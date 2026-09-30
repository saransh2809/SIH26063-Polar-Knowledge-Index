// Render react-icons to transparent PNGs (white glyphs for coloured circles; brand colours for logos).
const React = require('react')
const { renderToStaticMarkup } = require('react-dom/server')
const sharp = require('sharp')
const fa = require('react-icons/fa6')
const si = require('react-icons/si')

const WHITE = '#FFFFFF'
const glyphs = {
  cloudrain: fa.FaCloudRain, database: fa.FaDatabase, brain: fa.FaBrain, sliders: fa.FaSliders,
  heavyrain: fa.FaCloudShowersHeavy, mapdot: fa.FaMapLocationDot, check: fa.FaCircleCheck,
  display: fa.FaDisplay, users: fa.FaUsers, govt: fa.FaBuildingColumns, tractor: fa.FaTractor,
  flood: fa.FaHouseFloodWater, water: fa.FaWater, warning: fa.FaTriangleExclamation,
  shield: fa.FaShieldHalved, bulb: fa.FaLightbulb, server: fa.FaServer, laptop: fa.FaLaptop,
  scale: fa.FaScaleBalanced, magnify: fa.FaMagnifyingGlassChart, rocket: fa.FaRocket, plug: fa.FaPlug,
  clock: fa.FaClock, leaf: fa.FaLeaf, rupee: fa.FaIndianRupeeSign, people: fa.FaPeopleGroup,
  chip: fa.FaMicrochip, cap: fa.FaGraduationCap, flask: fa.FaFlask, book: fa.FaBook, link: fa.FaLink,
  satellite: fa.FaSatellite, gears: fa.FaGears, chartline: fa.FaChartLine, target: fa.FaBullseye,
  layers: fa.FaLayerGroup, bolt: fa.FaBolt, mountain: fa.FaMountain, wifioff: fa.FaWifi,
  vials: fa.FaVials, code: fa.FaCode, arrowright: fa.FaArrowRight, sitemap: fa.FaSitemap,
  cloud: fa.FaCloud, filecheck: fa.FaFileCircleCheck, globe: fa.FaEarthAsia,
}
const logos = {
  python: [si.SiPython, '#3776AB'], react: [si.SiReact, '#149ECA'], fastapi: [si.SiFastapi, '#009688'],
  typescript: [si.SiTypescript, '#3178C6'], leaflet: [si.SiLeaflet, '#199900'],
  sklearn: [si.SiScikitlearn, '#F7931E'], pandas: [si.SiPandas, '#150458'], numpy: [si.SiNumpy, '#013243'],
  pytorch: [si.SiPytorch, '#EE4C2C'], vite: [si.SiVite, '#646CFF'], pytest: [si.SiPytest, '#0A9EDC'],
}

async function render(name, Icon, color) {
  if (!Icon) { console.log('MISSING', name); return }
  const svg = renderToStaticMarkup(React.createElement(Icon, { color, size: 512 }))
  await sharp(Buffer.from(svg)).resize(512, 512, { fit: 'contain', background: { r: 0, g: 0, b: 0, alpha: 0 } })
    .png().toFile(`png/${name}.png`)
}

;(async () => {
  require('fs').mkdirSync('png', { recursive: true })
  for (const [n, I] of Object.entries(glyphs)) await render(n, I, WHITE)
  for (const [n, I] of Object.entries(glyphs)) await render(`${n}_navy`, I, '#1E2761')
  for (const [n, [I, c]] of Object.entries(logos)) await render(`logo_${n}`, I, c)
  console.log('done')
})()
