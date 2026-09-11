import { jsPDF } from 'jspdf'
import { autoTable } from 'jspdf-autotable'
import { aqiLabel, fmtDateLong } from './aqi'

const VIOLET = [124, 58, 237]
const INK = [24, 24, 32]
const MUTED = [113, 113, 122]

/**
 * Builds a one-page-ish PDF snapshot of the Overview dashboard for the
 * currently selected area, from data already fetched for that page — no
 * separate fetch, nothing invented. Historical / live / predicted labeling
 * mirrors what's shown on screen.
 */
export function downloadOverviewReport({ state, area, data }) {
  const doc = new jsPDF({ unit: 'pt', format: 'a4' })
  const pageW = doc.internal.pageSize.getWidth()
  const margin = 40
  let y = 0

  // ---- header -------------------------------------------------------
  doc.setFillColor(...INK)
  doc.rect(0, 0, pageW, 78, 'F')
  doc.setTextColor(255, 255, 255)
  doc.setFont('helvetica', 'bold')
  doc.setFontSize(18)
  doc.text('SMART AQI', margin, 34)
  doc.setFont('helvetica', 'normal')
  doc.setFontSize(10)
  doc.setTextColor(200, 190, 245)
  doc.text('Air quality report', margin, 50)
  doc.setFontSize(9)
  doc.setTextColor(210, 210, 220)
  doc.text(`${area}, ${state}`, margin, 65)
  doc.text(`Generated ${fmtDateLong(new Date().toISOString())}`, pageW - margin, 65, { align: 'right' })
  y = 100

  const cur = data.current
  const fc = data.forecast
  const adv = data.advisory

  // ---- current AQI ----------------------------------------------------
  doc.setTextColor(...INK)
  doc.setFont('helvetica', 'bold')
  doc.setFontSize(13)
  doc.text('Current AQI', margin, y)
  doc.setFont('helvetica', 'normal')
  doc.setFontSize(9)
  doc.setTextColor(...MUTED)
  const statusTag = cur?.available ? (cur.is_live ? 'LIVE · CPCB' : 'HISTORICAL · CPCB') : 'NOT AVAILABLE'
  doc.text(statusTag, pageW - margin, y, { align: 'right' })
  y += 20

  if (cur?.available) {
    doc.setTextColor(...VIOLET)
    doc.setFont('helvetica', 'bold')
    doc.setFontSize(30)
    doc.text(`${Math.round(cur.AQI)}`, margin, y + 20)
    doc.setFontSize(12)
    doc.setTextColor(...INK)
    doc.text(aqiLabel(cur.AQI), margin + 70, y + 18)
    doc.setFont('helvetica', 'normal')
    doc.setFontSize(9)
    doc.setTextColor(...MUTED)
    doc.text(`as of ${fmtDateLong(cur.as_of)}`, margin + 70, y + 32)
    y += 46

    const pollutantRows = Object.entries(cur.pollutants || {})
      .filter(([, v]) => v != null)
      .map(([k, v]) => [k, `${Math.round(v)} µg/m³`])
    if (pollutantRows.length) {
      autoTable(doc, {
        startY: y,
        head: [['Pollutant', 'Concentration']],
        body: pollutantRows,
        margin: { left: margin, right: margin },
        theme: 'plain',
        styles: { fontSize: 9, cellPadding: 4, textColor: INK },
        headStyles: { textColor: VIOLET, fontStyle: 'bold', lineWidth: 0.5, lineColor: [230, 225, 250] },
        tableLineColor: [230, 225, 250], tableLineWidth: 0.5,
      })
      y = doc.lastAutoTable.finalY + 18
    }
  } else {
    doc.setFont('helvetica', 'normal')
    doc.setFontSize(9)
    doc.setTextColor(...MUTED)
    doc.text('No current reading available for this area.', margin, y + 10)
    y += 26
  }

  // ---- 7-day forecast ---------------------------------------------------
  doc.setFont('helvetica', 'bold')
  doc.setFontSize(13)
  doc.setTextColor(...INK)
  doc.text('7-Day Forecast', margin, y)
  doc.setFont('helvetica', 'normal')
  doc.setFontSize(9)
  doc.setTextColor(...MUTED)
  doc.text(fc?.forecast_available ? `PREDICTED · Model: ${fc.model}` : 'NOT AVAILABLE', pageW - margin, y, { align: 'right' })
  y += 14

  if (fc?.forecast_available) {
    autoTable(doc, {
      startY: y,
      head: [['Horizon', 'Date', 'AQI', 'Category', 'Range']],
      body: fc.days.map((d) => [
        `+${d.horizon_day}d`,
        fmtDateLong(d.forecast_date),
        Math.round(d.predicted_AQI),
        aqiLabel(d.predicted_AQI),
        `${Math.round(d.lower)}–${Math.round(d.upper)}`,
      ]),
      margin: { left: margin, right: margin },
      theme: 'plain',
      styles: { fontSize: 9, cellPadding: 4, textColor: INK },
      headStyles: { textColor: VIOLET, fontStyle: 'bold', lineWidth: 0.5, lineColor: [230, 225, 250] },
      tableLineColor: [230, 225, 250], tableLineWidth: 0.5,
    })
    y = doc.lastAutoTable.finalY + 12
    doc.setFontSize(8)
    doc.setTextColor(...MUTED)
    doc.text('Predictions, not measurements. Horizon (+1d…+7d) counts from this station\'s own last', margin, y)
    y += 11
    doc.text('data point, which can lag today\'s calendar date — treat +1d…+7d as the reliable label.', margin, y)
    y += 22
  } else {
    doc.setFontSize(9)
    doc.setTextColor(...MUTED)
    doc.text(fc?.reason || 'No forecast available for this area.', margin, y + 8)
    y += 26
  }

  // ---- health advisory ----------------------------------------------
  if (y > 680) { doc.addPage(); y = 40 }
  doc.setFont('helvetica', 'bold')
  doc.setFontSize(13)
  doc.setTextColor(...INK)
  doc.text('Health Advisory', margin, y)
  y += 18

  if (adv?.available) {
    doc.setFont('helvetica', 'bold')
    doc.setFontSize(10.5)
    doc.text(adv.air_quality_status || 'Guidance', margin, y)
    y += 16

    doc.setFont('helvetica', 'normal')
    doc.setFontSize(9)
    doc.setTextColor(...INK)
    const outdoor = doc.splitTextToSize(`Outdoor activity: ${adv.outdoor_activity || '—'}`, pageW - margin * 2)
    doc.text(outdoor, margin, y)
    y += outdoor.length * 12 + 8

    if (adv.respiratory_precautions?.length) {
      doc.setFont('helvetica', 'bold')
      doc.setFontSize(9)
      doc.text('Respiratory precautions:', margin, y)
      y += 13
      doc.setFont('helvetica', 'normal')
      adv.respiratory_precautions.slice(0, 5).forEach((g) => {
        const lines = doc.splitTextToSize(`• ${g}`, pageW - margin * 2 - 10)
        doc.text(lines, margin + 8, y)
        y += lines.length * 12
      })
      y += 6
    }

    if (adv.disclaimer) {
      doc.setFontSize(8)
      doc.setTextColor(...MUTED)
      const disc = doc.splitTextToSize(adv.disclaimer, pageW - margin * 2)
      doc.text(disc, margin, y)
      y += disc.length * 10
    }
  } else {
    doc.setFont('helvetica', 'normal')
    doc.setFontSize(9)
    doc.setTextColor(...MUTED)
    doc.text('No health advisory available for this area.', margin, y)
  }

  // ---- footer on every page -----------------------------------------
  const pageCount = doc.internal.getNumberOfPages()
  for (let i = 1; i <= pageCount; i++) {
    doc.setPage(i)
    const h = doc.internal.pageSize.getHeight()
    doc.setDrawColor(230, 225, 250)
    doc.line(margin, h - 34, pageW - margin, h - 34)
    doc.setFont('helvetica', 'normal')
    doc.setFontSize(7.5)
    doc.setTextColor(...MUTED)
    doc.text('SMART AQI — informational use only, not medical advice. Historical data: CPCB (Kaggle 2015–2020).',
      margin, h - 22)
    doc.text(`Page ${i} of ${pageCount}`, pageW - margin, h - 22, { align: 'right' })
  }

  const fname = `smart-aqi-report_${area}_${state}_${new Date().toISOString().slice(0, 10)}`
    .replace(/[^a-z0-9_-]+/gi, '-')
  doc.save(`${fname}.pdf`)
}
