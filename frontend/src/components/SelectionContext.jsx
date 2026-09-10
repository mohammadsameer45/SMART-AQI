import { createContext, useContext, useEffect, useState } from 'react'
import { geo } from '../api/endpoints'

const SelCtx = createContext(null)
const LS = 'smartaqi_selection'

export function SelectionProvider({ children }) {
  const [states, setStates] = useState([])
  const [state, setState] = useState('')
  const [areaLevel, setAreaLevel] = useState('city')
  const [areas, setAreas] = useState([])
  const [area, setArea] = useState('')

  useEffect(() => {
    geo.states().then((list) => {
      setStates(list)
      let saved = {}
      try { saved = JSON.parse(localStorage.getItem(LS) || '{}') } catch { /* ignore */ }
      setState(saved.state && list.includes(saved.state) ? saved.state : (list[0] || ''))
      if (saved.area) setArea(saved.area)
    }).catch(() => {})
  }, [])

  useEffect(() => {
    if (!state) return
    geo.areas(state).then((r) => {
      setAreaLevel(r.level)
      setAreas(r.items)
      setArea((cur) => (cur && r.items.includes(cur) ? cur : r.items[0] || ''))
    }).catch(() => { setAreas([]); setArea('') })
  }, [state])

  useEffect(() => {
    try { localStorage.setItem(LS, JSON.stringify({ state, area })) } catch { /* ignore */ }
  }, [state, area])

  return (
    <SelCtx.Provider value={{ states, state, setState, areas, area, setArea, areaLevel }}>
      {children}
    </SelCtx.Provider>
  )
}

export const useSelection = () => useContext(SelCtx)
