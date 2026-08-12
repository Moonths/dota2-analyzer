export function heroImg(path) {
  if (!path) return ''
  if (path.startsWith('http')) return path
  return __IMG_HOST__ + path
}
