// frontend/js/player.js
import { secondsToDisplay } from './utils.js';

export function initPlayer({ previewPlayer, previewVideoWrapper, subOverlay, videoRatioBadge, previewResText, getCues, setLastActiveCueId, getLastActiveCueId, cueCardsContainer }) {

  previewPlayer.addEventListener('loadedmetadata', () => {
    const w = previewPlayer.videoWidth;
    const h = previewPlayer.videoHeight;
    if (w && h) {
      let ratioLabel = `${w}x${h}`;
      const ratio = w / h;
      if (Math.abs(ratio - 16 / 9) < 0.05) ratioLabel += ' (16:9 Ngang)';
      else if (Math.abs(ratio - 9 / 16) < 0.05) ratioLabel += ' (9:16 Dọc)';
      else if (Math.abs(ratio - 1) < 0.05) ratioLabel += ' (1:1 Vuông)';
      else if (Math.abs(ratio - 4 / 3) < 0.05) ratioLabel += ' (4:3)';
      if (videoRatioBadge) videoRatioBadge.textContent = ratioLabel;
      if (previewResText) previewResText.textContent = `${w}x${h} px`;
      previewVideoWrapper.style.aspectRatio = `${w} / ${h}`;
    }
  });

  previewPlayer.addEventListener('timeupdate', () => {
    const cur = previewPlayer.currentTime;
    const cues = getCues();
    const activeCue = cues.find(c => cur >= c.start && cur <= c.end);

    if (activeCue && activeCue.text) {
      subOverlay.textContent = activeCue.text;
      subOverlay.style.display = 'block';
      if (activeCue.id !== getLastActiveCueId()) {
        setLastActiveCueId(activeCue.id);
        cueCardsContainer.querySelectorAll('.cue-card').forEach(el =>
          el.classList.remove('ring-2', 'ring-indigo-500', 'border-indigo-500', 'bg-indigo-950/20'));
        const activeCardEl = cueCardsContainer.querySelector(`.cue-card[data-id="${activeCue.id}"]`);
        if (activeCardEl) {
          activeCardEl.classList.add('ring-2', 'ring-indigo-500', 'border-indigo-500', 'bg-indigo-950/20');
          activeCardEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
      }
    } else {
      subOverlay.textContent = '';
      subOverlay.style.display = 'none';
      if (getLastActiveCueId() !== null) {
        setLastActiveCueId(null);
        cueCardsContainer.querySelectorAll('.cue-card').forEach(el =>
          el.classList.remove('ring-2', 'ring-indigo-500', 'border-indigo-500', 'bg-indigo-950/20'));
      }
    }
  });

  return {
    syncLiveOverlay() {
      const cur = previewPlayer.currentTime;
      const cues = getCues();
      const activeCue = cues.find(c => cur >= c.start && cur <= c.end);
      if (activeCue && activeCue.text) {
        subOverlay.textContent = activeCue.text;
        subOverlay.style.display = 'block';
      } else {
        subOverlay.textContent = '';
        subOverlay.style.display = 'none';
      }
    }
  };
}
