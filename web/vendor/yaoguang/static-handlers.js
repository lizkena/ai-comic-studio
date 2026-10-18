
        (function(){
            try {
                var theme = localStorage.getItem('studio_theme') || localStorage.getItem('canvas_theme') || 'light';
                if(theme === 'dark') {
                    document.documentElement.classList.add('theme-dark');
                    document.documentElement.classList.add('studio-theme-dark');
                }
            } catch(e) {}
        })();
    
document.addEventListener("DOMContentLoaded",()=>{
document.querySelector('[data-yg-handler="0"]')?.addEventListener("click",function(event){backToCanvasList()});
document.querySelector('[data-yg-handler="1"]')?.addEventListener("click",function(event){openSmartCanvasShortcuts()});
document.querySelector('[data-yg-handler="2"]')?.addEventListener("click",function(event){openSmartCanvasLog()});
document.querySelector('[data-yg-handler="3"]')?.addEventListener("click",function(event){closeSmartWorkflowTransferModal()});
document.querySelector('[data-yg-handler="4"]')?.addEventListener("click",function(event){exportSelectedSmartWorkflow(false)});
document.querySelector('[data-yg-handler="5"]')?.addEventListener("click",function(event){exportSelectedSmartWorkflow(true)});
document.querySelector('[data-yg-handler="6"]')?.addEventListener("click",function(event){closeSmartCanvasLog()});
document.querySelector('[data-yg-handler="7"]')?.addEventListener("click",function(event){event.stopPropagation()});
document.querySelector('[data-yg-handler="8"]')?.addEventListener("click",function(event){closeSmartCanvasLog()});
document.querySelector('[data-yg-handler="9"]')?.addEventListener("click",function(event){closeSmartCanvasShortcuts()});
document.querySelector('[data-yg-handler="10"]')?.addEventListener("click",function(event){event.stopPropagation()});
document.querySelector('[data-yg-handler="11"]')?.addEventListener("click",function(event){closeSmartCanvasShortcuts()});
document.querySelector('[data-yg-handler="12"]')?.addEventListener("click",function(event){closeImageEditor()});
document.querySelector('[data-yg-handler="13"]')?.addEventListener("click",function(event){undoEditDrawing()});
document.querySelector('[data-yg-handler="14"]')?.addEventListener("click",function(event){redoEditDrawing()});
document.querySelector('[data-yg-handler="15"]')?.addEventListener("click",function(event){clearEditDrawing()});
document.querySelector('[data-yg-handler="16"]')?.addEventListener("click",function(event){setBrushTool('free')});
document.querySelector('[data-yg-handler="17"]')?.addEventListener("click",function(event){setBrushTool('rect')});
document.querySelector('[data-yg-handler="18"]')?.addEventListener("click",function(event){setBrushTool('ellipse')});
document.querySelector('[data-yg-handler="19"]')?.addEventListener("click",function(event){setBrushTool('label')});
document.querySelector('[data-yg-handler="20"]')?.addEventListener("click",function(event){setBrushTool('text')});
document.querySelector('[data-yg-handler="21"]')?.addEventListener("click",function(event){undoEditDrawing()});
document.querySelector('[data-yg-handler="22"]')?.addEventListener("click",function(event){redoEditDrawing()});
document.querySelector('[data-yg-handler="23"]')?.addEventListener("click",function(event){clearEditDrawing()});
document.querySelector('[data-yg-handler="24"]')?.addEventListener("click",function(event){setGridOperationMode('split')});
document.querySelector('[data-yg-handler="25"]')?.addEventListener("click",function(event){setGridOperationMode('join')});
document.querySelector('[data-yg-handler="26"]')?.addEventListener("click",function(event){toggleGridCustomMode()});
document.querySelector('[data-yg-handler="27"]')?.addEventListener("click",function(event){applyGridPreset(1, 2)});
document.querySelector('[data-yg-handler="28"]')?.addEventListener("click",function(event){applyGridPreset(2, 1)});
document.querySelector('[data-yg-handler="29"]')?.addEventListener("click",function(event){applyGridPreset(2, 2)});
document.querySelector('[data-yg-handler="30"]')?.addEventListener("click",function(event){applyGridPreset(2, 3)});
document.querySelector('[data-yg-handler="31"]')?.addEventListener("click",function(event){applyGridPreset(3, 2)});
document.querySelector('[data-yg-handler="32"]')?.addEventListener("click",function(event){applyGridPreset(3, 3)});
document.querySelector('[data-yg-handler="33"]')?.addEventListener("click",function(event){applyGridJoinPreset(1, 2)});
document.querySelector('[data-yg-handler="34"]')?.addEventListener("click",function(event){applyGridJoinPreset(2, 1)});
document.querySelector('[data-yg-handler="35"]')?.addEventListener("click",function(event){applyGridJoinPreset(2, 2)});
document.querySelector('[data-yg-handler="36"]')?.addEventListener("click",function(event){applyGridJoinPreset(2, 3)});
document.querySelector('[data-yg-handler="37"]')?.addEventListener("click",function(event){applyGridJoinPreset(3, 2)});
document.querySelector('[data-yg-handler="38"]')?.addEventListener("click",function(event){applyGridJoinPreset(3, 3)});
document.querySelector('[data-yg-handler="39"]')?.addEventListener("click",function(event){resetGridJoinLayout()});
document.querySelector('[data-yg-handler="40"]')?.addEventListener("click",function(event){setGridJoinOutputSize(1024)});
document.querySelector('[data-yg-handler="41"]')?.addEventListener("click",function(event){setGridJoinOutputSize(2048)});
document.querySelector('[data-yg-handler="42"]')?.addEventListener("click",function(event){setGridJoinOutputSize(4096)});
document.querySelector('[data-yg-handler="43"]')?.addEventListener("click",function(event){setGridCustomOrientation('h')});
document.querySelector('[data-yg-handler="44"]')?.addEventListener("click",function(event){setGridCustomOrientation('v')});
document.querySelector('[data-yg-handler="45"]')?.addEventListener("click",function(event){undoGridCustomLine()});
document.querySelector('[data-yg-handler="46"]')?.addEventListener("click",function(event){clearGridCustomLines()});
document.querySelector('[data-yg-handler="47"]')?.addEventListener("click",function(event){navigatePreviewImage(-1)});
document.querySelector('[data-yg-handler="48"]')?.addEventListener("click",function(event){navigatePreviewImage(1)});
document.querySelector('[data-yg-handler="49"]')?.addEventListener("click",function(event){downloadPreviewImage()});
document.querySelector('[data-yg-handler="50"]')?.addEventListener("click",function(event){downloadPreviewGroup()});
document.querySelector('[data-yg-handler="51"]')?.addEventListener("click",function(event){togglePanoramaPreview()});
document.querySelector('[data-yg-handler="52"]')?.addEventListener("click",function(event){exportPanoramaFrame()});
document.querySelector('[data-yg-handler="53"]')?.addEventListener("click",function(event){togglePreviewCompare()});
document.querySelector('[data-yg-handler="54"]')?.addEventListener("dblclick",function(event){resetImageEditZoom()});
document.querySelector('[data-yg-handler="55"]')?.addEventListener("click",function(event){exportVideoFrame('first')});
document.querySelector('[data-yg-handler="56"]')?.addEventListener("click",function(event){exportVideoFrame('current')});
document.querySelector('[data-yg-handler="57"]')?.addEventListener("click",function(event){exportVideoFrame('last')});
document.querySelector('[data-yg-handler="58"]')?.addEventListener("click",function(event){closeImageEditor()});
document.querySelector('[data-yg-handler="59"]')?.addEventListener("click",function(event){applyImageEdit()});
});
