// frontend/js/utils.js
export function pad(num, size = 2) {
  let s = num + "";
  while (s.length < size) s = "0" + s;
  return s;
}

export function timeStringToSeconds(tStr) {
  const parts = tStr.trim().replace(',', '.').split(':');
  if (parts.length === 3) {
    return parseFloat(parts[0]) * 3600 + parseFloat(parts[1]) * 60 + parseFloat(parts[2]);
  }
  return 0;
}

export function secondsToSRT(seconds) {
  const totalSec = Math.floor(seconds);
  const millis = Math.min(999, Math.round((seconds - totalSec) * 1000));
  const hrs = Math.floor(totalSec / 3600);
  const mins = Math.floor((totalSec % 3600) / 60);
  const secs = totalSec % 60;
  return `${pad(hrs)}:${pad(mins)}:${pad(secs)},${pad(millis, 3)}`;
}

export function secondsToVTT(seconds) {
  const totalSec = Math.floor(seconds);
  const millis = Math.min(999, Math.round((seconds - totalSec) * 1000));
  const hrs = Math.floor(totalSec / 3600);
  const mins = Math.floor((totalSec % 3600) / 60);
  const secs = totalSec % 60;
  return `${pad(hrs)}:${pad(mins)}:${pad(secs)}.${pad(millis, 3)}`;
}

export function secondsToDisplay(seconds) {
  const totalSec = Math.floor(seconds);
  const millis = Math.min(999, Math.round((seconds - totalSec) * 1000));
  const mins = Math.floor((totalSec % 3600) / 60);
  const secs = totalSec % 60;
  return `${pad(mins)}:${pad(secs)}.${pad(millis, 3)}`;
}

export function hexToAssBgr(hex) {
  const cleaned = hex.replace('#', '').trim();
  if (cleaned.length === 6) {
    const r = cleaned.substring(0, 2).toUpperCase();
    const g = cleaned.substring(2, 4).toUpperCase();
    const b = cleaned.substring(4, 6).toUpperCase();
    return `&H00${b}${g}${r}&`;
  }
  return '&H0000FFFF&';
}

export function parseSRT(srtText) {
  const parsed = [];
  const normalized = (srtText || '').replace(/\r\n/g, '\n').replace(/\r/g, '\n');
  const blocks = normalized.trim().split(/\n\s*\n/);
  let idCounter = 1;
  for (const block of blocks) {
    const lines = block.trim().split('\n');
    if (lines.length >= 2) {
      let timeLineIdx = -1;
      for (let i = 0; i < lines.length; i++) {
        if (lines[i].includes('-->')) { timeLineIdx = i; break; }
      }
      if (timeLineIdx !== -1) {
        const timeParts = lines[timeLineIdx].split('-->');
        if (timeParts.length === 2) {
          const start = timeStringToSeconds(timeParts[0]);
          const end = timeStringToSeconds(timeParts[1]);
          const text = lines.slice(timeLineIdx + 1).join('\n').trim();
          if (text || end > start) {
            parsed.push({ id: idCounter++, start, end,
              startTimeStr: timeParts[0].trim(), endTimeStr: timeParts[1].trim(), text });
          }
        }
      }
    }
  }
  return parsed;
}

export function serializeCuesToSRT(cueList) {
  return cueList.map((cue, idx) =>
    `${idx + 1}\n${secondsToSRT(cue.start)} --> ${secondsToSRT(cue.end)}\n${cue.text.trim()}`
  ).join('\n\n') + '\n';
}

export function serializeCuesToVTT(cueList) {
  const body = cueList.map((cue, idx) =>
    `${idx + 1}\n${secondsToVTT(cue.start)} --> ${secondsToVTT(cue.end)}\n${cue.text.trim()}`
  ).join('\n\n');
  return `WEBVTT\n\n${body}\n`;
}

export function downloadBlob(content, filename, mimeType) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = filename;
  document.body.appendChild(a); a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
