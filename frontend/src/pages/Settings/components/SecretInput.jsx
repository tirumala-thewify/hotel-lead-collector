import { useState } from 'react'

function SecretInput({ id, label, value, onChange, placeholder }) {
  const [visible, setVisible] = useState(false)
  return (
    <div className="secret-field">
      <label htmlFor={id}>{label}</label>
      <div className="secret-control">
        <input
          id={id}
          type={visible ? 'text' : 'password'}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder={placeholder}
          autoComplete="off"
        />
        <button type="button" onClick={() => setVisible((current) => !current)}>
          {visible ? 'Hide' : 'Show'}
        </button>
      </div>
    </div>
  )
}

export default SecretInput
