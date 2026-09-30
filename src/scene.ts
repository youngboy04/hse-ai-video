// Procedural, explicitly synthetic camera scene. No external images or cloud assets.
export function warehouse(
  ctx: CanvasRenderingContext2D,
  w: number,
  h: number,
  variant: number,
  time: number,
) {
  ctx.save();
  ctx.scale(w / 900, h / 500);
  const g = ctx.createLinearGradient(0, 0, 0, 500);
  g.addColorStop(0, "#182833");
  g.addColorStop(0.48, "#687574");
  g.addColorStop(1, "#485355");
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, 900, 500);
  const vx = 460 + variant * 18,
    vy = 120;
  ctx.fillStyle = "#88928c";
  ctx.fillRect(225, 82, 490, 143);
  ctx.fillStyle = "#a7b3ab";
  for (let i = 0; i < 8; i++) ctx.fillRect(250 + i * 54, 98, 37, 42);
  ctx.fillStyle = "#34434a";
  for (let i = 0; i < 6; i++) ctx.fillRect(270 + i * 69, 162, 46, 63);
  const path = (points: number[][], fill: string, stroke?: string) => {
    ctx.beginPath();
    points.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
    ctx.closePath();
    ctx.fillStyle = fill;
    ctx.fill();
    if (stroke) {
      ctx.strokeStyle = stroke;
      ctx.stroke();
    }
  };
  path(
    [
      [0, 0],
      [900, 0],
      [715, 82],
      [225, 82],
    ],
    "#26343b",
  );
  ctx.lineWidth = 2;
  ctx.strokeStyle = "#142630";
  for (let x = -500; x < 1500; x += 100) {
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(vx, vy);
    ctx.stroke();
  }
  for (let y = 10; y < 100; y += 23) {
    ctx.lineWidth = 8 - y * 0.05;
    ctx.strokeStyle = "#566165";
    ctx.beginPath();
    ctx.moveTo(0, y * 1.7);
    ctx.lineTo(900, y * 0.8);
    ctx.stroke();
  }
  for (let i = 0; i < 5; i++) {
    ctx.strokeStyle = "rgba(237,245,218,.8)";
    ctx.lineWidth = 4;
    ctx.beginPath();
    ctx.moveTo(70 + i * 176, 30);
    ctx.lineTo(150 + i * 138, 76);
    ctx.stroke();
  }
  path(
    [
      [0, 240],
      [225, 202],
      [715, 202],
      [900, 240],
      [900, 500],
      [0, 500],
    ],
    "#697270",
  );
  for (let x = -1000; x < 2200; x += 180) {
    ctx.strokeStyle = "#7b8380";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(vx, 200);
    ctx.lineTo(x, 500);
    ctx.stroke();
  }
  for (const y of [248, 295, 355, 430]) {
    ctx.strokeStyle = "#77807b";
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(900, y);
    ctx.stroke();
  }
  // Receding columns, rack beams, pallets and storage bins.
  for (let j = 3; j >= 0; j--) {
    const x = 25 + j * 56,
      y = 80 + j * 28,
      bottom = 420 - j * 49,
      bw = 85 - j * 13;
    path(
      [
        [x, y],
        [x + bw, y + 14],
        [x + bw, bottom - 20],
        [x, bottom],
      ],
      j % 2 ? "#3c4d51" : "#34474c",
    );
    ctx.fillStyle = "#a58245";
    for (let k = 0; k < 3; k++) {
      const yy = y + 33 + (k * (bottom - y - 50)) / 3;
      ctx.fillRect(x + 7, yy, bw - 12, 25 - j * 3);
      ctx.fillStyle = "#414f50";
      ctx.fillRect(x + 12, yy + 4, bw - 23, 3);
      ctx.fillStyle = "#a58245";
    }
    ctx.fillStyle = "#b87637";
    for (let k = 0; k < 4; k++)
      ctx.fillRect(x, y + 16 + (k * (bottom - y - 19)) / 3, bw, 5);
    ctx.fillStyle = "#263d46";
    ctx.fillRect(x, y, 7, bottom - y);
    ctx.fillRect(x + bw - 5, y, 6, bottom - y);
  }
  for (let j = 3; j >= 0; j--) {
    const x = 795 - j * 51,
      y = 76 + j * 28,
      bottom = 436 - j * 53,
      bw = 99 - j * 13;
    path(
      [
        [x, y + 12],
        [x + bw, y],
        [x + bw, bottom],
        [x, bottom - 18],
      ],
      "#294149",
    );
    for (let k = 0; k < 3; k++) {
      ctx.fillStyle = k === 1 ? "#6f8c88" : "#9e9276";
      ctx.fillRect(
        x + 9,
        y + 34 + (k * (bottom - y - 60)) / 3,
        bw - 16,
        34 - j * 4,
      );
      ctx.fillStyle = "#687f7f";
      ctx.fillRect(x + 12, y + 38 + (k * (bottom - y - 60)) / 3, bw - 23, 3);
    }
    ctx.fillStyle = "#ac7540";
    for (let k = 0; k < 4; k++)
      ctx.fillRect(x, y + 13 + (k * (bottom - y - 15)) / 3, bw, 5);
    ctx.fillStyle = "#20373e";
    ctx.fillRect(x, y, 7, bottom - y);
    ctx.fillRect(x + bw - 6, y - 2, 7, bottom - y + 3);
  }
  for (const x of [192, 696]) {
    path(
      [
        [x, 60],
        [x + 15, 64],
        [x + 15, 285],
        [x, 294],
      ],
      "#84918c",
    );
    ctx.fillStyle = "#383e34";
    ctx.fillRect(x, 250, 15, 42);
    ctx.strokeStyle = "#d6ae43";
    ctx.lineWidth = 4;
    for (let y = 251; y < 290; y += 13) {
      ctx.beginPath();
      ctx.moveTo(x, y);
      ctx.lineTo(x + 15, y + 10);
      ctx.stroke();
    }
  }
  ctx.strokeStyle = "#dbb84f";
  ctx.lineWidth = 4;
  ctx.beginPath();
  ctx.moveTo(340, 223);
  ctx.lineTo(236, 500);
  ctx.moveTo(562, 223);
  ctx.lineTo(707, 500);
  ctx.stroke();
  // Work cell and machinery.
  path(
    [
      [550, 219],
      [656, 215],
      [677, 297],
      [553, 307],
    ],
    "#435f5c",
  );
  path(
    [
      [553, 244],
      [672, 235],
      [672, 304],
      [553, 319],
    ],
    "#344e4c",
  );
  ctx.fillStyle = "#8aaba1";
  ctx.fillRect(574, 202, 59, 53);
  ctx.fillStyle = "#304b4d";
  ctx.fillRect(582, 210, 39, 26);
  ctx.fillStyle = "#8fc38f";
  ctx.fillRect(614, 241, 4, 4);
  path(
    [
      [299, 251],
      [349, 242],
      [374, 306],
      [312, 321],
    ],
    "#a5a190",
  );
  path(
    [
      [312, 277],
      [371, 268],
      [371, 321],
      [312, 335],
    ],
    "#6c7164",
  );
  ctx.fillStyle = "#b6b6a0";
  for (let k = 0; k < 3; k++) ctx.fillRect(318, 284 + k * 13, 46, 5);
  // Low-contrast camera grain and vignette.
  ctx.fillStyle = "rgba(9,26,29,.04)";
  for (let y = 0; y < 500; y += 4) ctx.fillRect(0, y, 900, 1);
  const vignette = ctx.createRadialGradient(450, 230, 130, 450, 250, 530);
  vignette.addColorStop(0, "rgba(3,14,23,0)");
  vignette.addColorStop(1, "rgba(3,14,23,.55)");
  ctx.fillStyle = vignette;
  ctx.fillRect(0, 0, 900, 500);
  ctx.fillStyle = `rgba(80,130,150,${0.025 + Math.sin(time * 0.2) * 0.01})`;
  ctx.fillRect(0, 0, 900, 500);
  ctx.restore();
}

export function person(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  helmet: boolean | null,
  vest: boolean | null,
) {
  ctx.save();
  ctx.translate(x + w / 2, y);
  ctx.fillStyle = "rgba(8,20,24,.25)";
  ctx.beginPath();
  ctx.ellipse(3, h + 3, w * 0.55, h * 0.035, -0.1, 0, Math.PI * 2);
  ctx.fill();
  ctx.strokeStyle = "#243a45";
  ctx.lineWidth = w * 0.22;
  ctx.lineCap = "round";
  ctx.beginPath();
  ctx.moveTo(-w * 0.13, h * 0.57);
  ctx.lineTo(-w * 0.2, h * 0.95);
  ctx.moveTo(w * 0.13, h * 0.57);
  ctx.lineTo(w * 0.2, h * 0.95);
  ctx.stroke();
  ctx.strokeStyle = "#78817a";
  ctx.lineWidth = w * 0.17;
  ctx.beginPath();
  ctx.moveTo(-w * 0.3, h * 0.28);
  ctx.lineTo(-w * 0.4, h * 0.6);
  ctx.moveTo(w * 0.3, h * 0.28);
  ctx.lineTo(w * 0.4, h * 0.6);
  ctx.stroke();
  ctx.fillStyle = vest ? "#c3b943" : "#486476";
  ctx.beginPath();
  ctx.roundRect(-w * 0.3, h * 0.22, w * 0.6, h * 0.4, w * 0.09);
  ctx.fill();
  if (vest) {
    ctx.fillStyle = "#e0e7c2";
    ctx.fillRect(-w * 0.28, h * 0.44, w * 0.56, h * 0.04);
    ctx.fillRect(-w * 0.16, h * 0.23, w * 0.06, h * 0.37);
    ctx.fillRect(w * 0.11, h * 0.23, w * 0.06, h * 0.37);
  }
  ctx.fillStyle = "#b79c81";
  ctx.beginPath();
  ctx.ellipse(0, h * 0.145, w * 0.17, h * 0.09, 0, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = helmet ? "#e8c54d" : "#343330";
  ctx.beginPath();
  ctx.ellipse(0, h * 0.095, w * 0.22, h * 0.065, 0, Math.PI, Math.PI * 2);
  ctx.fill();
  if (helmet) ctx.fillRect(-w * 0.25, h * 0.09, w * 0.5, h * 0.035);
  ctx.restore();
}
