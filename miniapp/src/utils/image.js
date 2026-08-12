export function heroImg(path) {
  if (!path) return ''
  if (path.startsWith('http')) return path
  // 图片跟 API 走同一基地址（dev: localhost:8000/api, prod: maojike.me/dota-api）
  return __API_BASE__ + path
}
