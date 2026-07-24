export function findLastDefinedIndex(values) {
  for (let index = values.length - 1; index >= 0; index -= 1) {
    if (Number.isFinite(values[index])) return index;
  }
  return -1;
}

export function drawLine(ctx, values, xAt, scale, color, lineWidth = 1.5, dash = []) {
  ctx.strokeStyle = color;
  ctx.lineWidth = lineWidth;
  ctx.setLineDash(dash);
  ctx.beginPath();
  let started = false;
  values.forEach((value, index) => {
    if (!Number.isFinite(value)) return;
    if (!started) {
      ctx.moveTo(xAt(index), scale(value));
      started = true;
    } else {
      ctx.lineTo(xAt(index), scale(value));
    }
  });
  ctx.stroke();
  ctx.setLineDash([]);
}

export function drawArea(ctx, values, xAt, scale, baseY, strokeColor, fillColor) {
  const safeFirstIndex = values.findIndex((value) => Number.isFinite(value));
  const lastIndex = findLastDefinedIndex(values);
  if (safeFirstIndex < 0 || lastIndex < 0) return;

  ctx.beginPath();
  ctx.moveTo(xAt(safeFirstIndex), scale(values[safeFirstIndex]));
  for (let index = safeFirstIndex + 1; index <= lastIndex; index += 1) {
    if (!Number.isFinite(values[index])) continue;
    ctx.lineTo(xAt(index), scale(values[index]));
  }
  ctx.lineTo(xAt(lastIndex), baseY);
  ctx.lineTo(xAt(safeFirstIndex), baseY);
  ctx.closePath();
  ctx.fillStyle = fillColor;
  ctx.fill();
  drawLine(ctx, values, xAt, scale, strokeColor, 1.8);
}

export function fillBetweenSeries(
  ctx,
  upperValues,
  lowerValues,
  xAt,
  scale,
  fillAbove,
  fillBelow,
) {
  const flushSegment = (segment, isAbove) => {
    if (segment.length < 2) return;
    ctx.beginPath();
    ctx.moveTo(xAt(segment[0].index), scale(segment[0].upper));
    segment.forEach((point, pointIndex) => {
      if (pointIndex === 0) return;
      ctx.lineTo(xAt(point.index), scale(point.upper));
    });
    for (let index = segment.length - 1; index >= 0; index -= 1) {
      const point = segment[index];
      ctx.lineTo(xAt(point.index), scale(point.lower));
    }
    ctx.closePath();
    ctx.fillStyle = isAbove ? fillAbove : fillBelow;
    ctx.fill();
  };

  let segment = [];
  let currentAbove = null;
  upperValues.forEach((upper, index) => {
    const lower = lowerValues[index];
    if (!Number.isFinite(upper) || !Number.isFinite(lower)) {
      flushSegment(segment, currentAbove);
      segment = [];
      currentAbove = null;
      return;
    }
    const isAbove = upper >= lower;
    if (!segment.length || currentAbove === isAbove) {
      currentAbove = isAbove;
      segment.push({ index, upper, lower });
      return;
    }

    flushSegment(segment, currentAbove);
    const previousIndex = Math.max(index - 1, 0);
    segment = [{
      index: previousIndex,
      upper: upperValues[previousIndex],
      lower: lowerValues[previousIndex],
    }];
    currentAbove = isAbove;
    segment.push({ index, upper, lower });
  });
  flushSegment(segment, currentAbove);
}
