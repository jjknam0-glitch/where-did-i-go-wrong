import { lazy, Suspense, useEffect } from 'react'
import { Route, Routes, useLocation } from 'react-router-dom'
import { Layout } from './components/Layout'
import { Spinner } from './components/ui'
import Home from './pages/Home'

const Capture = lazy(() => import('./pages/Capture'))
const Confirm = lazy(() => import('./pages/Confirm'))
const Result = lazy(() => import('./pages/Result'))
const TypeWork = lazy(() => import('./pages/TypeWork'))
const History = lazy(() => import('./pages/History'))
const HistoryDetail = lazy(() => import('./pages/HistoryDetail'))
const Progress = lazy(() => import('./pages/Progress'))
const Practice = lazy(() => import('./pages/Practice'))
const TestPrep = lazy(() => import('./pages/TestPrep'))
const Lessons = lazy(() => import('./pages/Lessons'))
const LessonPage = lazy(() => import('./pages/Lesson'))
const Share = lazy(() => import('./pages/Share'))
const SharedView = lazy(() => import('./pages/SharedView'))
const Family = lazy(() => import('./pages/Family'))
const Plans = lazy(() => import('./pages/Plans'))
const Account = lazy(() => import('./pages/Account'))
const Privacy = lazy(() => import('./pages/Privacy'))
const HowItWorks = lazy(() => import('./pages/HowItWorks'))
const More = lazy(() => import('./pages/More'))
const NotFound = lazy(() => import('./pages/NotFound'))

function ScrollToTop() {
  const { pathname } = useLocation()
  useEffect(() => {
    window.scrollTo(0, 0)
  }, [pathname])
  return null
}

export default function App() {
  const { pathname } = useLocation()
  const fullScreen = pathname === '/capture'
  const routes = (
    <Suspense fallback={<Spinner />}>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/capture" element={<Capture />} />
        <Route path="/confirm" element={<Confirm />} />
        <Route path="/result" element={<Result />} />
        <Route path="/type" element={<TypeWork />} />
        <Route path="/history" element={<History />} />
        <Route path="/history/:id" element={<HistoryDetail />} />
        <Route path="/progress" element={<Progress />} />
        <Route path="/practice" element={<Practice />} />
        <Route path="/test-prep" element={<TestPrep />} />
        <Route path="/lessons" element={<Lessons />} />
        <Route path="/lessons/:id" element={<LessonPage />} />
        <Route path="/share" element={<Share />} />
        <Route path="/s/:id" element={<SharedView />} />
        <Route path="/family" element={<Family />} />
        <Route path="/plans" element={<Plans />} />
        <Route path="/account" element={<Account />} />
        <Route path="/privacy" element={<Privacy />} />
        <Route path="/how-it-works" element={<HowItWorks />} />
        <Route path="/more" element={<More />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </Suspense>
  )
  return (
    <>
      <ScrollToTop />
      {fullScreen ? routes : <Layout>{routes}</Layout>}
    </>
  )
}
