const fs = require('fs');
const path = require('path');

function createSvgIcon(size) {
  const r = Math.round(size * 0.2);
  const fontSize = Math.round(size * 0.4);
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">
  <rect width="${size}" height="${size}" rx="${r}" fill="#7c3aed"/>
  <text x="50%" y="55%" text-anchor="middle" dominant-baseline="middle" fill="white" font-family="Arial" font-weight="bold" font-size="${fontSize}">W</text>
</svg>`;
}

const sizes = [16, 48, 128];
const dir = path.join(__dirname, 'public', 'icons');

sizes.forEach(size => {
  const svg = createSvgIcon(size);
  fs.writeFileSync(path.join(dir, `icon${size}.png`), Buffer.from(svg));
  console.log(`Created icon${size}.png (SVG placeholder)`);
});
