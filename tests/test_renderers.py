import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).parents[1]/"skills/decksmith/scripts"))
from create_deck import renderer_runtime, powerpoint_preview, SpecError
from doctor import inspect
from runtime_probe import test_export as export_probe


class RendererTests(unittest.TestCase):
    def test_probe_distinguishes_pdf_failure_after_png_success(self):
        def fail_pdf(pptx, directory, scene, **kwargs):
            preview=directory/'preview';preview.mkdir()
            (preview/'slide-01.png').write_bytes(b'\x89PNG\r\n\x1a\n'+b'\0'*8+(1280).to_bytes(4,'big')+(720).to_bytes(4,'big'))
            raise SpecError('PDF_EXPORT_FAILED: fixture')
        with patch('runtime_probe.renderer_runtime',return_value={'powershell':'fixture'}), \
                patch('runtime_probe.executable',return_value='node'), \
                patch('runtime_probe.run'), patch('runtime_probe.powerpoint_preview',side_effect=fail_pdf):
            result=export_probe()
        self.assertTrue(result['png']['ready'])
        self.assertFalse(result['pdf']['ready'])
        self.assertIn('PDF_EXPORT_FAILED',result['error'])

    def test_none_requires_no_converter(self):
        with patch("create_deck.executable",side_effect=AssertionError("unexpected lookup")):
            self.assertEqual(renderer_runtime("none"),{})

    def test_powerpoint_rejects_mac_and_wsl(self):
        for platform in ("darwin","linux"):
            with patch("sys.platform",platform), self.assertRaisesRegex(SpecError,"native Windows"):
                renderer_runtime("powerpoint")

    def test_windows_probe_and_no_libreoffice(self):
        with patch("sys.platform","win32"), patch("create_deck.executable",return_value="powershell.exe") as locate, patch("create_deck.run",return_value='{"ready":true}') as run:
            self.assertEqual(renderer_runtime("powerpoint"),{"powershell":"powershell.exe"})
            locate.assert_called_once_with("powershell.exe","DECKSMITH_POWERSHELL")
            self.assertIn("-Probe",run.call_args.args[0])
            self.assertNotIn("-ExecutionPolicy",run.call_args.args[0])

    def test_probe_timeout_and_failure(self):
        with patch("sys.platform","win32"), patch("create_deck.executable",return_value="powershell.exe"):
            with patch("create_deck.run",side_effect=subprocess.TimeoutExpired("probe",30)), self.assertRaisesRegex(SpecError,"timed out"):
                renderer_runtime("powerpoint")
            with patch("create_deck.run",side_effect=SpecError("policy blocked")), self.assertRaisesRegex(SpecError,"policy blocked"):
                renderer_runtime("powerpoint")

    def test_doctor_none(self):
        with patch("doctor.executable",return_value="node") as locate, patch("doctor.run",return_value='{"ready":true}'):
            result=inspect("none")
            self.assertTrue(result["renderer"]["ready"])
            self.assertNotIn("soffice",result)
            self.assertNotIn("pdftoppm",result)
            self.assertTrue(all(call.args[0]=="node" for call in locate.call_args_list))

    def test_doctor_powerpoint_failure(self):
        with patch("doctor.executable",return_value="node"), patch("doctor.run",return_value='{"ready":true}'), patch("doctor.renderer_runtime",side_effect=SpecError("not installed")):
            result=inspect("powerpoint")
            self.assertFalse(result["renderer"]["ready"])
            self.assertNotIn("soffice",result)

    def test_export_adapter_output_contract(self):
        for export_pdf in (False,True):
            with self.subTest(pdf=export_pdf), tempfile.TemporaryDirectory(prefix="日本語 space ") as raw:
                directory=Path(raw)
                scene={"canvas":{"width":1920,"height":1080},"slides":[{}]}
                def fake_export(command, **kwargs):
                    request=json.loads(Path(command[-1]).read_text())
                    self.assertEqual(request["count"],1)
                    self.assertEqual(bool(request["pdf"]),export_pdf)
                    # Header fixture only: no claim to test PowerPoint or real PNG rendering.
                    header=b"\x89PNG\r\n\x1a\n"+b"\0"*8+(1920).to_bytes(4,"big")+(1080).to_bytes(4,"big")
                    (Path(request["preview"])/"slide-01.png").write_bytes(header)
                    if export_pdf: Path(request["pdf"]).write_bytes(b"%PDF-test")
                    return "{}"
                with patch("create_deck.run",side_effect=fake_export):
                    result=powerpoint_preview(directory/"candidate.pptx",directory,scene,"powershell.exe",export_pdf)
                self.assertTrue((result/"slide-01.png").exists())

    def test_export_rejects_missing_pages_and_timeout(self):
        for failure in (None, subprocess.TimeoutExpired("export",180)):
            with tempfile.TemporaryDirectory() as raw:
                with patch("create_deck.run",side_effect=failure,return_value="{}"), self.assertRaises(SpecError):
                    powerpoint_preview(Path(raw)/"candidate.pptx",Path(raw),{"canvas":{"width":1920,"height":1080},"slides":[{}]},"powershell.exe",False)
