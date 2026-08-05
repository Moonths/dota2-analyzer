const API = 'https://maojike.me/dota-api'

export function heroImg(path) {
  if (!path) return ''
  if (path.startsWith('http')) return path
  return API + path
}
