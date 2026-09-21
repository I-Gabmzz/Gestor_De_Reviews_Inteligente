import { BrowserRouter, Route, Routes } from 'react-router-dom'

function Home() {
  return <h1>Gestor Inteligente de Reviews</h1>
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Home />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App

