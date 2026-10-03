import { BrowserRouter, Route, Routes } from 'react-router-dom'

import DashboardPage from './pages/DashboardPage.jsx'
import ImportReviewsPage from './pages/ImportReviewsPage.jsx'
import LoginPage from './pages/LoginPage.jsx'
import ManualReviewPage from './pages/ManualReviewPage.jsx'
import ReviewsPage from './pages/ReviewsPage.jsx'
import UsersPage from './pages/UsersPage.jsx'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LoginPage />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/imports" element={<ImportReviewsPage />} />
        <Route path="/reviews" element={<ReviewsPage />} />
        <Route path="/reviews/new" element={<ManualReviewPage />} />
        <Route path="/users" element={<UsersPage />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
