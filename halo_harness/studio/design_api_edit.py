"""halo_harness.studio.design_api_edit -- the direct text edit of the React
Design section (Halo 3.0.7.0 R3b). `/design-files/<slug>/<artboard>/index.html
?edit=pick` (the current version only) carries PICK_SCRIPT: a double-click on
a text in the sandboxed prototype posts `halo-design-pick` to Studio with
where that text sits (the element path from <body>, the text node's index,
the text, its box in the frame). Studio opens its own inline editor there;
Save edits the same node in the page's source and posts the page to the
existing `text-edit` route, which saves it as a new version. The script is
wrapped in the `<!--halo-edit-->` markers, so `text-edit` strips it if a page
ever comes back with it.
"""

from __future__ import annotations

PICK_SCRIPT = """<!--halo-edit--><script id="halo-edit-script">(function(){
function at(x,y){if(document.caretRangeFromPoint){var r=document.caretRangeFromPoint(x,y);return r&&r.startContainer;}
if(document.caretPositionFromPoint){var p=document.caretPositionFromPoint(x,y);return p&&p.offsetNode;}return null;}
function path(el){var out=[];while(el&&el!==document.body){var i=0,s=el;while((s=s.previousElementSibling))i++;out.unshift(i);el=el.parentElement;}return el===document.body?out:null;}
document.addEventListener("dblclick",function(e){var t=at(e.clientX,e.clientY),el,n=-1,box;
if(t&&t.nodeType===3&&t.nodeValue.trim()){el=t.parentElement;n=Array.prototype.indexOf.call(el.childNodes,t);var g=document.createRange();g.selectNodeContents(t);box=g.getBoundingClientRect();}
else{el=e.target;if(!el||el.nodeType!==1||el.children.length||!el.textContent.trim())return;box=el.getBoundingClientRect();}
var p=path(el);if(!p)return;e.preventDefault();var s=window.getSelection();if(s)s.removeAllRanges();
parent.postMessage({type:"halo-design-pick",path:p,node:n,text:n>=0?t.nodeValue:el.textContent,tag:el.tagName.toLowerCase(),
x:box.left,y:box.top,w:box.width,h:box.height,vw:innerWidth,vh:innerHeight},"*");},true);})();</script><!--/halo-edit-->"""


def inject(text: str, script: str = PICK_SCRIPT) -> str:
    """The page with `script` just before its closing </body> (or at its end)."""
    i = text.lower().rfind("</body>")
    return text[:i] + script + text[i:] if i >= 0 else text + script
