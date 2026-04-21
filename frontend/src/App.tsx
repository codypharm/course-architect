import { useEffect } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import {
  RedirectToSignIn,
  SignIn,
  SignUp,
  useAuth,
} from '@clerk/clerk-react'
import { api } from '@/lib/api'
import LandingPage from '@/pages/LandingPage'
import DashboardPage from '@/pages/DashboardPage'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, staleTime: 0 },
  },
})

/** Registers the Axios Bearer-token interceptor once per mount.
 *  Must live inside ClerkProvider so useAuth() is available. */
function ApiInterceptorProvider({ children }: { children: React.ReactNode }) {
  const { getToken } = useAuth()

  useEffect(() => {
    const id = api.interceptors.request.use(async (config) => {
      const token = await getToken()
      if (token) config.headers.Authorization = `Bearer ${token}`
      return config
    })
    return () => api.interceptors.request.eject(id)
  }, [getToken])

  return <>{children}</>
}

/** Redirects unauthenticated users to Clerk sign-in, preserving the destination URL. */
function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isSignedIn, isLoaded } = useAuth()
  if (!isLoaded) return null
  if (!isSignedIn) return <RedirectToSignIn />
  return <>{children}</>
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <ApiInterceptorProvider>
          <Routes>
            <Route path="/" element={<LandingPage />} />
            <Route
              path="/sign-in/*"
              element={<SignIn routing="path" path="/sign-in" />}
            />
            <Route
              path="/sign-up/*"
              element={<SignUp routing="path" path="/sign-up" />}
            />
            <Route
              path="/dashboard"
              element={<ProtectedRoute><DashboardPage /></ProtectedRoute>}
            />
            <Route
              path="/courses/:threadId"
              element={<ProtectedRoute><DashboardPage /></ProtectedRoute>}
            />
          </Routes>
        </ApiInterceptorProvider>
      </BrowserRouter>
    </QueryClientProvider>
  )
}

export default App
