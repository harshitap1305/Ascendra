import { useMemo } from 'react'
import { eachDayOfInterval, subWeeks, format, getDay, startOfWeek, isSameDay } from 'date-fns'

const DAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
const WEEKS = 16  // show last 16 weeks

function intensityColor(hours) {
  if (!hours || hours === 0) return '#1e293b'  // slate-800 empty
  if (hours < 1) return '#312e81'              // very light
  if (hours < 2) return '#4338ca'              // day started
  if (hours < 4) return '#6366f1'              // good day
  return '#818cf8'                              // great day
}

export default function StudyCalendarHeatmap({ dailyHours = {} }) {
  // Build a grid: 16 weeks × 7 days, starting from 16 weeks ago
  const { weeks } = useMemo(() => {
    const endDate = new Date()
    const startDate = subWeeks(startOfWeek(endDate), WEEKS - 1)
    const allDays = eachDayOfInterval({ start: startDate, end: endDate })

    // Group into weeks
    const weeksArr = []
    let currentWeek = []
    let dayOfWeekIndex = getDay(startDate)

    // Pad the first week if it doesn't start on Sunday
    for (let i = 0; i < dayOfWeekIndex; i++) {
      currentWeek.push(null)
    }
    for (const day of allDays) {
      currentWeek.push(day)
      if (getDay(day) === 6) {
        weeksArr.push(currentWeek)
        currentWeek = []
      }
    }
    if (currentWeek.length > 0) weeksArr.push(currentWeek)
    return { weeks: weeksArr }
  }, [])

  const CELL = 13
  const GAP = 2

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-secondary">Study Calendar</h3>
        {/* Intensity legend */}
        <div className="flex items-center gap-1.5 text-xs text-secondary/70">
          <span>Less</span>
          {['#1e293b', '#312e81', '#4338ca', '#6366f1', '#818cf8'].map((c, i) => (
            <div key={i} style={{ background: c, width: 11, height: 11, borderRadius: 2 }} />
          ))}
          <span>More</span>
        </div>
      </div>

      <div className="overflow-x-auto">
        <div className="flex gap-0.5">
          {/* Day labels */}
          <div className="flex flex-col gap-[2px] mr-1" style={{ paddingTop: 2 }}>
            {DAYS.map((d, i) => (
              <div
                key={d}
                className="text-slate-600 text-[9px] leading-none flex items-center"
                style={{ height: CELL + GAP }}
              >
                {i % 2 === 1 ? d : ''}
              </div>
            ))}
          </div>

          {/* Week columns */}
          {weeks.map((week, wi) => (
            <div key={wi} className="flex flex-col gap-[2px]">
              {Array.from({ length: 7 }, (_, di) => {
                const day = week[di]
                if (!day) return <div key={di} style={{ width: CELL, height: CELL }} />
                const dateStr = format(day, 'yyyy-MM-dd')
                const hours = dailyHours[dateStr] || 0
                const color = intensityColor(hours)
                return (
                  <div
                    key={di}
                    title={`${format(day, 'MMM d')} — ${hours ? `${hours}h studied` : 'No study'}`}
                    style={{
                      width: CELL,
                      height: CELL,
                      background: color,
                      borderRadius: 2,
                      cursor: hours > 0 ? 'pointer' : 'default',
                    }}
                  />
                )
              })}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
