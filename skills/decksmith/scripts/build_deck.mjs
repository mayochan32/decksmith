// Portable scene renderer. No provider SDK, styles, layout selection or network calls.
import fs from "node:fs/promises";
import path from "node:path";
import { createRequire } from "node:module";
const require = process.env.DECKSMITH_NODE_MODULES
  ? createRequire(path.join(path.resolve(process.env.DECKSMITH_NODE_MODULES), "__decksmith__.cjs"))
  : createRequire(import.meta.url);
const PptxGenJS = require("pptxgenjs");
const { imageSize } = require("image-size");
if (process.argv.includes("--check")) {
  console.log(JSON.stringify({engine:"pptxgenjs", ready:true}));
  process.exit(0);
}
const args = Object.fromEntries(process.argv.slice(2).reduce((out,v,i,a)=>{
  if (i%2===0) out.push([v.replace(/^--/,""),a[i+1]]); return out;
},[]));
const spec=JSON.parse(await fs.readFile(args.spec,"utf8"));
const deck=new PptxGenJS();
deck.defineLayout({name:"SCENE",width:spec.canvas.width/96,height:spec.canvas.height/96});
deck.layout="SCENE";
deck.author="DeckSmith";
deck.subject="Editable presentation";
const paint = value => {
  if (!value || value==="none") return {color:"FFFFFF",transparency:100};
  return {color:value.slice(1,7),transparency:value.length===9 ? (1-parseInt(value.slice(7),16)/255)*100 : 0};
};
const style = e => ({
  fontFace:e.font,fontSize:e.size*0.75,...paint(e.color),bold:e.bold??false,italic:e.italic??false,
});
for (const data of spec.slides) {
  const slide=deck.addSlide();
  slide.background=paint(data.background);
  for (const e of data.elements) {
    const box={x:e.x/96,y:e.y/96,w:e.width/96,h:e.height/96,rotate:((e.rotation??0)%360+360)%360,objectName:e.id};
    if (e.type==="text") {
      const runs=e.runs?.map(r=>({text:r.text,options:style({...e,...r})})) ?? e.text;
      slide.addText(runs,{...box,...style(e),margin:0,breakLine:false,
        align:e.align??"left",valign:e.vertical??"top",lineSpacingMultiple:e.line_spacing??1.05,
        paraSpaceAfterPt:0,paraSpaceBeforePt:0,fit:"none",isTextBox:true,
      });
    } else if (e.type==="image") {
      const ext=path.extname(e.path).toLowerCase();
      if (![".png",".jpg",".jpeg"].includes(ext)) throw new Error("Portable images require PNG or JPEG: "+e.id);
      const bytes=await fs.readFile(e.path);
      const dimensions=imageSize(bytes);
      const dataUri="image/"+(ext===".png"?"png":"jpeg")+";base64,"+bytes.toString("base64");
      const scale=Math.min(box.w/dimensions.width,box.h/dimensions.height);
      const sizing=e.fit==="cover"
        ? {sizing:{type:"cover",w:box.w,h:box.h}}
        : {x:box.x+(box.w-dimensions.width*scale)/2,y:box.y+(box.h-dimensions.height*scale)/2,
           w:dimensions.width*scale,h:dimensions.height*scale};
      if (!dimensions.width || !dimensions.height) throw new Error("Invalid image: "+e.id);
      slide.addImage({...box,...sizing,data:dataUri,altText:e.alt});
    } else {
      const opts={...box,fill:paint(e.fill),line:{...paint(e.stroke),width:(e.stroke_width??0)*0.75}};
      if (!e.stroke || e.stroke==="none" || !e.stroke_width) opts.line={type:"none"};
      let geometry=e.geometry;
      if (e.type==="path") {
        geometry="custGeom";
        opts.points=e.points.map(([x,y])=>({x:x/96,y:y/96})).concat(e.closed?[{close:true}]:[]);
      } else if (e.radius!==undefined) {
        if (!["rect","roundRect"].includes(e.geometry)) throw new Error("Radius only supported on rectangles");
        geometry=e.radius ? "roundRect":"rect"; opts.rectRadius=e.radius/96;
      }
      slide.addShape(geometry,opts);
    }
  }
  if(data.notes) slide.addNotes(data.notes);
}
await deck.writeFile({fileName:args.output});
