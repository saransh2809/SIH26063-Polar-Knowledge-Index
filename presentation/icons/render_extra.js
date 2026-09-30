// Extra icons for the NCPOR deck: white glyphs for coloured circles, navy variants, brand-colour logos.
const React = require('react')
const { renderToStaticMarkup } = require('react-dom/server')
const sharp = require('sharp')
const fa = require('react-icons/fa6')
const si = require('react-icons/si')

const glyphs = {
  snowflake: fa.FaSnowflake, ship: fa.FaShip, newspaper: fa.FaNewspaper, filepdf: fa.FaFilePdf,
  language: fa.FaLanguage, usercheck: fa.FaUserCheck, rss: fa.FaRss, image: fa.FaImage, school: fa.FaSchool,
  robot: fa.FaRobot, clipboard: fa.FaClipboardCheck, lock: fa.FaLock, eye: fa.FaEye,
  question: fa.FaCircleQuestion, history: fa.FaClockRotateLeft, archive: fa.FaBoxArchive,
  search: fa.FaMagnifyingGlass, hashtag: fa.FaHashtag, microscope: fa.FaMicroscope, compass: fa.FaCompass,
  pen: fa.FaPenNib, quote: fa.FaQuoteLeft, scan: fa.FaExpand, sitemap2: fa.FaDiagramProject,
  xmark: fa.FaCircleXmark, museum: fa.FaLandmark, video: fa.FaVideo, listcheck: fa.FaListCheck,
}
const logos = {
  postgresql: [si.SiPostgresql, '#4169E1'], nextdotjs: [si.SiNextdotjs, '#000000'],
  tailwind: [si.SiTailwindcss, '#06B6D4'], docker: [si.SiDocker, '#2496ED'],
  gemini: [si.SiGooglegemini, '#8E75B2'], huggingface: [si.SiHuggingface, '#FFB000'],
  sqlalchemy: [si.SiSqlalchemy, '#D71F00'],
}

async function render(name, Icon, color) {
  if (!Icon) { console.log('MISSING', name); return }
  const svg = renderToStaticMarkup(React.createElement(Icon, { color, size: 512 }))
  await sharp(Buffer.from(svg)).resize(512, 512, { fit: 'contain', background: { r: 0, g: 0, b: 0, alpha: 0 } })
    .png().toFile(`png/${name}.png`)
}

;(async () => {
  for (const [n, I] of Object.entries(glyphs)) await render(n, I, '#FFFFFF')
  for (const [n, I] of Object.entries(glyphs)) await render(`${n}_navy`, I, '#1E2761')
  for (const [n, [I, c]] of Object.entries(logos)) await render(`logo_${n}`, I, c)
  console.log('done')
})()
