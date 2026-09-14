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

  // Load available states
  useEffect(() => {
    geo.states()
      .then((list) => {
        console.log('States API response:', list)

        setStates(list)

        let saved = {}

        try {
          saved = JSON.parse(
            localStorage.getItem(LS) || '{}'
          )
        } catch {
          // Ignore invalid saved selection
        }

        setState(
          saved.state && list.includes(saved.state)
            ? saved.state
            : (list[0] || '')
        )

        if (saved.area) {
          setArea(saved.area)
        }
      })
      .catch((err) => {
        console.error('Failed to load states:', err)
        setStates([])
        setState('')
      })
  }, [])

  // Load districts/cities whenever the state changes
  useEffect(() => {
    if (!state) {
      setAreas([])
      setArea('')
      return
    }

    console.log('Loading areas for state:', state)

    geo.areas(state)
      .then((r) => {
        console.log('Areas API response:', r)

        setAreaLevel(r.level)
        setAreas(r.items)

        setArea((cur) => (
          cur && r.items.includes(cur)
            ? cur
            : (r.items[0] || '')
        ))
      })
      .catch((err) => {
        console.error(
          'Failed to load areas for state:',
          state,
          err
        )

        setAreas([])
        setArea('')
      })
  }, [state])

  // Save current selection
  useEffect(() => {
    try {
      localStorage.setItem(
        LS,
        JSON.stringify({
          state,
          area,
        })
      )
    } catch {
      // Ignore localStorage errors
    }
  }, [state, area])

  return (
    <SelCtx.Provider
      value={{
        states,
        state,
        setState,
        areas,
        area,
        setArea,
        areaLevel,
      }}
    >
      {children}
    </SelCtx.Provider>
  )
}

export const useSelection = () => useContext(SelCtx)