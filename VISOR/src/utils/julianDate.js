export function dateToJulianDay(date) {
  const start = new Date(date.getFullYear(), 0, 0)
  const diff = date - start
  const oneDay = 1000 * 60 * 60 * 24
  return Math.floor(diff / oneDay).toString().padStart(3, '0')
}

export function formatTimestamp(dateStr) {
  const date = new Date(dateStr)
  const utc = date.toISOString().slice(11, 16) + ' UTC'
  const lt = date.toLocaleTimeString('es-EC', {
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'America/Guayaquil',
  })
  return `${lt} LT / ${utc}`
}

export function formatDateTimeFull(dateStr) {
  const date = new Date(dateStr)
  const datePart = date.toLocaleDateString('es-EC', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    timeZone: 'America/Guayaquil',
  })
  const timePart = date.toLocaleTimeString('es-EC', {
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'America/Guayaquil',
  })
  return { date: datePart, time: timePart }
}

export function formatTimeShort(dateStr) {
  const date = new Date(dateStr)
  return date.toLocaleTimeString('es-EC', {
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'America/Guayaquil',
  })
}

export function formatDateShort(dateStr) {
  const date = new Date(dateStr)
  return date.toLocaleDateString('es-EC', {
    day: '2-digit',
    month: 'short',
    timeZone: 'America/Guayaquil',
  })
}

export function getLocalDate(dateStr) {
  const date = new Date(dateStr)
  return date.toLocaleDateString('es-EC', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    timeZone: 'America/Guayaquil',
  })
}

export function getDateRange(endDate, hoursBack) {
  const end = new Date(endDate)
  const start = new Date(end.getTime() - hoursBack * 60 * 60 * 1000)
  return { start, end }
}

export function parseDatetimeLocal(str) {
  return new Date(str)
}

export function toDatetimeLocalString(date) {
  const d = new Date(date)
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset())
  return d.toISOString().slice(0, 16)
}

export function getDaysInRange(start, end) {
  const days = []
  const current = new Date(start)
  current.setHours(0, 0, 0, 0)
  const endDate = new Date(end)
  endDate.setHours(23, 59, 59, 999)

  while (current <= endDate) {
    days.push({
      year: current.getFullYear(),
      julianDay: dateToJulianDay(current),
    })
    current.setDate(current.getDate() + 1)
  }
  return days
}
