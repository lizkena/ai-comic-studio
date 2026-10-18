(() => {
    const defaultColor = '#4f86a6';
    const normalizeColor = value => /^#[0-9a-f]{6}$/i.test(String(value || '')) ? value.toLowerCase() : defaultColor;
    const textColor = value => {
        const hex = normalizeColor(value).slice(1);
        const channels = [0, 2, 4].map(i => parseInt(hex.slice(i, i + 2), 16) / 255);
        return channels[0] * .299 + channels[1] * .587 + channels[2] * .114 > .62 ? '#17212f' : '#ffffff';
    };
    let dialog = null;
    let resolveCurrent = null;
    function buildDialog() {
        dialog = document.createElement('dialog');
        dialog.className = 'canvas-group-appearance-dialog';
        dialog.setAttribute('aria-labelledby', 'canvasGroupAppearanceTitle');
        dialog.innerHTML = `<form method="dialog">
            <h2 id="canvasGroupAppearanceTitle">分组名称和颜色</h2>
            <label for="canvasGroupName">名称</label>
            <input id="canvasGroupName" name="title" maxlength="80" required autocomplete="off" placeholder="输入分组名称">
            <label for="canvasGroupColor">颜色</label>
            <div class="canvas-group-color-row"><input id="canvasGroupColor" name="color" type="color" aria-label="自定义分组颜色"><span class="canvas-group-color-value"></span></div>
            <div class="canvas-group-color-presets" role="group" aria-label="分组预设颜色">${[
                ['蓝色', '#4f86a6'], ['紫色', '#8b6bb1'], ['绿色', '#4f927a'],
                ['橙色', '#ce8347'], ['红色', '#b96871'], ['灰色', '#64748b']
            ].map(([label, color]) => `<button type="button" data-group-color="${color}" style="--swatch:${color}" aria-label="${label}" title="${label}" aria-pressed="false"></button>`).join('')}</div>
            <div class="canvas-group-appearance-preview" aria-label="分组标题预览"></div>
            <div class="canvas-group-appearance-actions"><button type="button" data-group-cancel>取消</button><button class="primary" type="submit">保存</button></div>
        </form>`;
        document.body.appendChild(dialog);
        const name = dialog.querySelector('[name="title"]');
        const color = dialog.querySelector('[name="color"]');
        const updatePreview = () => {
            const value = normalizeColor(color.value);
            const preview = dialog.querySelector('.canvas-group-appearance-preview');
            preview.textContent = name.value.trim() || '未命名分组';
            preview.style.backgroundColor = value;
            preview.style.color = textColor(value);
            dialog.querySelector('.canvas-group-color-value').textContent = value.toUpperCase();
            dialog.querySelectorAll('[data-group-color]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.groupColor === value)));
        };
        name.addEventListener('input', updatePreview);
        color.addEventListener('input', updatePreview);
        dialog.querySelectorAll('[data-group-color]').forEach(button => button.addEventListener('click', () => { color.value = button.dataset.groupColor; updatePreview(); }));
        dialog.querySelector('form').addEventListener('submit', event => {
            event.preventDefault();
            const title = name.value.trim();
            if (!title) { name.setCustomValidity('请输入分组名称'); name.reportValidity(); return; }
            finish({title, color:normalizeColor(color.value)});
        });
        name.addEventListener('input', () => name.setCustomValidity(''));
        dialog.querySelector('[data-group-cancel]').addEventListener('click', () => finish(null));
        dialog.addEventListener('cancel', event => { event.preventDefault(); finish(null); });
        dialog.addEventListener('close', () => { if (!dialog.open && resolveCurrent) finish(null); });
        dialog.addEventListener('keydown', event => event.stopPropagation());
        dialog.updatePreview = updatePreview;
    }
    function finish(result) {
        const resolve = resolveCurrent;
        resolveCurrent = null;
        if (dialog?.open) dialog.close();
        resolve?.(result);
    }
    window.CanvasGroupAppearance = {
        normalizeColor, textColor,
        isOpen: () => Boolean(dialog?.open),
        open({title='智能分组', color=defaultColor, focus='title'} = {}) {
            if (!dialog) buildDialog();
            if (dialog.open) return Promise.resolve(null);
            const name = dialog.querySelector('[name="title"]');
            name.value = title;
            name.setCustomValidity('');
            dialog.querySelector('[name="color"]').value = normalizeColor(color);
            dialog.updatePreview();
            return new Promise(resolve => {
                resolveCurrent = resolve;
                dialog.showModal();
                if (focus === 'color') dialog.querySelector('[name="color"]').focus();
                else { name.focus(); name.select(); }
            });
        }
    };
})();
