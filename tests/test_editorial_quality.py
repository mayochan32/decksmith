import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/decksmith/scripts'))
from compile_spec import SpecError
from editorial_quality import check_editorial_links, reading_outline, repetitions


class EditorialQualityTests(unittest.TestCase):
    def slide(self):
        return {'id': 's', 'elements': [
            {'id': 'title', 'type': 'text', 'role': 'heading', 'text': '申込みと参加確定'},
            {'id': 'table', 'type': 'table', 'headers': ['方法', '条件'],
             'rows': [['Web', '申込みだけでは確定しない\n運営担当からの結果通知を確認'],
                      ['窓口', '受付だけでは確定しない\n運営担当からの結果通知を確認']]},
            {'id': 'note', 'type': 'text', 'role': 'caption', 'text': 'どちらも、運営担当からの結果通知を確認します。'}]}

    def test_table_explanation_repeated_in_a_footer_is_located_without_deletion(self):
        slide = self.slide(); before = copy.deepcopy(slide)
        found = repetitions(slide)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]['elements'], ['table', 'note'])
        self.assertEqual({m['locations'][0] for m in found[0]['matches']}, {'table/cell/1/1', 'table/cell/2/1'})
        self.assertEqual(slide, before)

    def test_shared_conditions_within_one_table_are_not_duplicate_warnings(self):
        slide = self.slide(); slide['elements'].pop()
        self.assertEqual(repetitions(slide), [])

    def test_short_role_names_numbers_and_page_labels_are_not_repetitions(self):
        slide = {'id': 's', 'elements': [{'id': str(i), 'type': 'text', 'text': '受付窓口 0 01 / 04'} for i in range(3)]}
        self.assertEqual(repetitions(slide), [])

    def test_different_qualifiers_are_not_inferred_to_be_equivalent(self):
        slide = {'id': 's', 'elements': [
            {'id': 'a', 'type': 'text', 'text': '参加が確定する前に限り本人が内容を変更できます'},
            {'id': 'b', 'type': 'text', 'text': '参加が確定した後に本人が内容を変更できません'}]}
        self.assertEqual(repetitions(slide), [])

    def test_rich_text_repeat_is_visible_content(self):
        slide = self.slide(); note = slide['elements'][-1]
        note.pop('text'); note['runs'] = [{'text': '運営担当からの'}, {'text': '結果通知を確認します'}]
        self.assertEqual(len(repetitions(slide)), 1)

    def test_explicit_headline_and_evidence_must_be_actual_elements(self):
        slide = self.slide()
        memo = {'headline': 'title', 'visible_evidence': ['table'], 'emphasis_targets': ['table'],
                'takeaway': '両方法とも結果通知を確認', 'source_basis': '原稿の参加確定条件',
                'continuity': '非確定の説明の後に方法ごとの条件を示す'}
        check_editorial_links({'communication': memo}, slide)
        for field, invalid in [('headline', 'table'), ('visible_evidence', ['missing']),
                               ('emphasis_targets', ['table', 'table']), ('continuity', '')]:
            with self.subTest(field=field), self.assertRaises(SpecError):
                check_editorial_links({'communication': {**memo, field: invalid}}, slide)

    def test_legacy_memo_does_not_become_a_new_requirement(self):
        check_editorial_links({'communication': 'Existing free-form notes'}, self.slide())
        check_editorial_links({'communication': {'audience_question': '題目だけで十分なページ'}}, self.slide())

    def test_outline_reports_actual_headings_and_keeps_unstated_claims_empty(self):
        plan = {'slides': [{'id': 's', 'communication': {'headline': 'title', 'takeaway': '結果通知を確認',
            'source_basis': '原稿2ページ目', 'visible_evidence': ['table'], 'emphasis_targets': ['table'],
            'continuity': '前のページの非確定条件を具体化'}}]}
        scene = {'slides': [self.slide(), {'id': 'second', 'elements': [{'id': 'topic', 'type': 'text', 'role': 'heading', 'text': '集計対象'}]}]}
        result = reading_outline(scene, plan)
        self.assertEqual(result[0]['visible_headings'], [{'element': 'title', 'text': '申込みと参加確定'}])
        self.assertEqual(result[0]['visible_evidence'], ['table'])
        self.assertEqual(result[1]['visible_headings'][0]['text'], '集計対象')
        self.assertIsNone(result[1]['declared_takeaway'])


if __name__ == '__main__':
    unittest.main()
