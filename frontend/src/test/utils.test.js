import { describe, it, expect } from 'vitest'
import { bandFor, aqiLabel, aqiDisplay, aqiColor } from '../utils/aqi'

describe('aqi utils', () => {
  it('maps values to CPCB bands', () => {
    expect(bandFor(0).label).toBe('Good')
    expect(bandFor(50).label).toBe('Good')
    expect(bandFor(51).label).toBe('Satisfactory')
    expect(bandFor(200).label).toBe('Moderate')
    expect(bandFor(201).label).toBe('Poor')
    expect(bandFor(999).label).toBe('Severe')
  })

  it('handles null / NaN', () => {
    expect(bandFor(null)).toBeNull()
    expect(bandFor(NaN)).toBeNull()
    expect(aqiLabel(null)).toBe('—')
    expect(aqiDisplay(null)).toBe('—')
  })

  it('caps display at 500 with a + marker', () => {
    expect(aqiDisplay(142)).toBe('142')
    expect(aqiDisplay(640)).toBe('500+')
  })

  it('returns a hex colour per band', () => {
    expect(aqiColor(30)).toMatch(/^#/)
    expect(aqiColor(30)).not.toBe(aqiColor(280))
  })
})
