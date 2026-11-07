/* Native PDF adapter for the frozen monthly packet; no accounting or source changes. */
(function(root){'use strict';
function create(model){
 const html=root.MonthlyReport.render(model),dom=new DOMParser().parseFromString(html,'text/html'),sections=[...dom.querySelectorAll('section')];
 const pdf=new root.jspdf.jsPDF({orientation:'landscape',unit:'pt',format:'a4'}),W=841.89,H=595.28;
 function text(value,x,y,size=9,color='#1B1E4A',bold=false){pdf.setFont('helvetica',bold?'bold':'normal');pdf.setFontSize(size);pdf.setTextColor(color);pdf.text(String(value).replace(/—/g,'-').replace(/·/g,' | '),x,y);}
 sections.forEach((section,index)=>{
  if(index)pdf.addPage();
  text(section.querySelector('h1').textContent,28,36,19,'#1B1E4A',true);
  text(section.querySelector('header p').textContent,28,55,9);
  const logo=section.querySelector('header img');if(logo)pdf.addImage(logo.src,'PNG',715,19,96,44);
  let cy=84;section.querySelectorAll('.card').forEach((card,i)=>{const height=i===2?108:83;const fill=i===0?'#1B1E4A':i===1?'#2D3691':'#FFFFFF',fg=i<2?'#FFFFFF':'#1B1E4A';pdf.setFillColor(fill);pdf.setDrawColor('#2D3691');pdf.rect(28,cy,145,height,'FD');text(card.querySelector('small').textContent,38,cy+20,8,fg);text(card.querySelector('strong').textContent,38,cy+46,16,fg,true);const p=card.querySelector('p');if(p){pdf.setFontSize(8);text(p.textContent.replace(/Invoices/,' | Invoices'),38,cy+72,7,fg);}cy+=height+12;});
  const main=section.querySelector('main');let y=84;
  const svg=main.querySelector('svg');if(svg){const sx=0.82,sy=0.65,ox=198,oy=y;svg.querySelectorAll('rect').forEach(r=>{pdf.setFillColor(r.getAttribute('fill'));pdf.rect(ox+Number(r.getAttribute('x'))*sx,oy+Number(r.getAttribute('y'))*sy,Number(r.getAttribute('width'))*sx,Number(r.getAttribute('height'))*sy,'F');});svg.querySelectorAll('text').forEach(t=>text(t.textContent,ox+Number(t.getAttribute('x'))*sx,oy+Number(t.getAttribute('y'))*sy,8));text('Year colors: light blue / gray / navy (oldest to current)',198,y+148,8);y+=163;}
  const table=main.querySelector('table');if(table){const rows=[...table.querySelectorAll('tr')],n=rows[0].children.length,width=610,first=n>3?190:290,other=(width-first)/(n-1);rows.forEach((row,ri)=>{const height=11.8;pdf.setFillColor(ri===0?'#1B1E4A':ri%2?'#FFFFFF':'#EDF2F8');pdf.rect(198,y,width,height,'F');[...row.children].forEach((cell,ci)=>{const cw=ci?other:first;let x=198+(ci?first+(ci-1)*other:0)+4;const value=cell.textContent;pdf.setFont('helvetica',ri===0?'bold':'normal');pdf.setFontSize(7.2);if(ci){pdf.setTextColor(ri===0?'#FFFFFF':'#1B1E4A');pdf.text(value.replace(/—/g,'-'),x+cw-8,y+8.5,{align:'right'});}else text(value,x,y+8.5,7.2,ri===0?'#FFFFFF':'#1B1E4A',ri===0);});y+=height;});}
  // Body disclosures and chart notes are copied verbatim from the same frozen HTML packet.
  main.querySelectorAll('p').forEach(p=>{pdf.setFontSize(9);const lines=pdf.splitTextToSize(p.textContent.replace(/—/g,'-'),610);pdf.setFont('helvetica','normal');pdf.setTextColor('#1B1E4A');pdf.text(lines,198,y+15);y+=lines.length*11+12;});
  text(section.querySelector('footer').textContent,28,H-23,7);text((index+1)+' / '+sections.length,W-65,H-23,8);
 });pdf.setProperties({title:model.config.company+' monthly report '+model.month,subject:'Frozen source '+model.sha256});return pdf;
}
root.MonthlyReportPDF={create};
})(window);
