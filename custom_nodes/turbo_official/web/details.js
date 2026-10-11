import { app } from '../../scripts/app.js';
import { ComfyWidgets } from '../../scripts/widgets.js';
app.registerExtension({
  name: 'TurboImageStudio.RunDetails',
  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData.name !== 'TurboRunDetails') return;
    const previous = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      previous?.apply(this, arguments);
      const w = ComfyWidgets.STRING(this, 'actual_settings', ['STRING', {multiline: true}], app).widget;
      w.value = 'Run the workflow to see actual settings and timings.';
      w.inputEl.readOnly = true;
      w.serialize = false;
      this.setSize([500, 420]);
    };
    const executed = nodeType.prototype.onExecuted;
    nodeType.prototype.onExecuted = function (message) {
      executed?.apply(this, arguments);
      const w = this.widgets?.find(w => w.name === 'actual_settings');
      if (w) w.value = message.text?.join('\n') || '';
      this.setDirtyCanvas(true, true);
    };
  }
});
