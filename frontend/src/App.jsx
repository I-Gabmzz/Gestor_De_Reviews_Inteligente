import { BrowserRouter, Route, Routes } from 'react-router-dom'

import DashboardPlaceholder from './pages/DashboardPlaceholder.jsx'
import LoginPage from './pages/LoginPage.jsx'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LoginPage />} />
        <Route path="/dashboard" element={<DashboardPlaceholder />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
