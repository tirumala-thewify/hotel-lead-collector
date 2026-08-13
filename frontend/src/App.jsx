import HomePage from './pages/Home/HomePage.jsx'
import SettingsPage from './pages/Settings/SettingsPage.jsx'

// ============================================================
// TOP-LEVEL PAGE SELECTION
// Keeps the existing pathname-based navigation in one small app shell.
// ============================================================
function App() {
  const Page = window.location.pathname === '/settings' ? SettingsPage : HomePage
  return <Page />
}

export default App
