import fs from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { Presentation, PresentationFile } from "@oai/artifact-tool";
const args=Object.fromEntries(process.argv.slice(2).reduce((out,v,i,a)=>{
  if(i%2===0) out.push([v.replace(/^--/,""),a[i+1]]); return out;
},[]));
const spec=JSON.parse(await fs.readFile(args.spec,"utf8"));
const {SKILL_DIR,TMP_DIR,RUNTIME_PYTHON}=process.env;
const utils=await import(pathToFileURL(path.join(SKILL_DIR,"container_tools/artifact_tool_utils.mjs")));
const deck=Presentation.create({slideSize:spec.canvas});
const fonts=new Set();
for(const data of spec.slides){
  const slide=deck.slides.add(); slide.background.fill=data.background;
  for(const e of data.elements){
    const position={left:e.x,top:e.y,width:e.width,height:e.height,rotation:e.rotation??0};
    if(e.type==="image"){
      const mime={".png":"image/png",".jpg":"image/jpeg",".jpeg":"image/jpeg",".webp":"image/webp"};
      slide.images.add({blob:await fs.readFile(e.path),contentType:mime[path.extname(e.path).toLowerCase()],
        alt:e.alt,prompt:e.prompt,fit:e.fit??"contain",position});
    }else if(e.type==="text"){
      fonts.add(e.font);
      const shape=slide.shapes.add({name:e.id,geometry:"textbox",position,fill:"none",line:{fill:"none",width:0}});
      shape.text.style={typeface:e.font,fontSize:e.size,color:e.color,bold:e.bold??false,
        italic:e.italic??false,alignment:e.align??"left",verticalAlignment:e.vertical??"top",
        autoFit:"none",wrap:"square",lineSpacing:e.line_spacing??1.05,insets:{top:0,right:0,bottom:0,left:0}};
      if(e.runs) shape.text.set([e.runs.map(r=>{
        if(r.font) fonts.add(r.font);
        return {run:r.text,textStyle:{typeface:r.font??e.font,fontSize:String(r.size??e.size)+"px",
          color:r.color??e.color,bold:r.bold??e.bold??false,italic:r.italic??e.italic??false}};
      })]);
      else shape.text=e.text;
    }else{
      const config={name:e.id,geometry:e.type==="path"?"custom":e.geometry,position,
        fill:e.fill??"none",line:{fill:e.stroke??"none",width:e.stroke_width??0}};
      if(e.radius!==undefined) config.borderRadius=e.radius;
      if(e.type==="path") config.customPaths=[{width:e.width,height:e.height,
        commands:e.points.map((p,i)=>({[i?"lineTo":"moveTo"]:{x:p[0],y:p[1]}})).concat(e.closed?[{close:{}}]:[])}];
      slide.shapes.add(config);
    }
  }
  if(data.notes) slide.speakerNotes.textFrame.setText(data.notes);
}
const output=path.resolve(args.output), previewDir=output.replace(/\.pptx$/i,".preview");
await fs.mkdir(previewDir,{recursive:true});
const candidate=path.join(TMP_DIR,"candidate.pptx");
await (await PresentationFile.exportPptx(deck)).save(candidate);
await utils.finalizePresentation({
  explicitTotalSlideCount:spec.slides.length,requiredNativeTableOwnerSlides:[],requiredNativeChartOwnerSlides:[],
  workspaceDir:path.resolve(args.workspace),candidatePath:candidate,finalPath:output,pythonExecutable:RUNTIME_PYTHON,
  integrityValidatorPath:path.join(SKILL_DIR,"container_tools/inspect_presentation_package_integrity.py"),
  layoutValidatorPath:path.join(SKILL_DIR,"container_tools/inspect_presentation_layout_geometry.py"),
  layoutArgs:["--expected-slide-size-emu",spec.canvas.width*9525+","+spec.canvas.height*9525,"--validate-heading-fit"],
  fontPolicy:{basis:"design",families:[...fonts]},verifyArtifactToolImport:true,
  receiptPath:path.join(TMP_DIR,"validation.json"),
});
for(let i=0;i<deck.slides.items.length;i++){
  const slide=deck.slides.items[i],prefix=path.join(previewDir,"slide-"+String(i+1).padStart(2,"0"));
  const png=await slide.export({format:"png",scale:1});
  await fs.writeFile(prefix+".png",new Uint8Array(await png.arrayBuffer()));
  await fs.writeFile(prefix+".layout.json",await(await slide.export({format:"layout"})).text());
}
await fs.writeFile(path.join(previewDir,"review-manifest.json"),JSON.stringify({
  status:"pending_visual_review",style_sha256:spec.style_sha256,structure_sha256:spec.structure_sha256,
  requirements:spec.requirements,slides:spec.slides.map((s,i)=>({id:s.id,
    preview:"slide-"+String(i+1).padStart(2,"0")+".png",
    intentional_overflow:s.elements.filter(e=>e.overflow_reason).map(e=>({id:e.id,reason:e.overflow_reason})),
    checks:["content","style fidelity","text fit","layering","image crop"],status:"pending"})),
},null,2));
console.log(JSON.stringify({output,previewDir,status:"pending_visual_review"}));
