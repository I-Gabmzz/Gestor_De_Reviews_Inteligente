import { BrowserRouter, Route, Routes } from 'react-router-dom'

import DashboardPlaceholder from './pages/DashboardPlaceholder.jsx'
import LoginPage from './pages/LoginPage.jsx'
import ReviewsPage from './pages/ReviewsPage.jsx'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LoginPage />} />
        <Route path="/dashboard" element={<DashboardPlaceholder />} />
        <Route path="/reviews" element={<ReviewsPage />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
