import { Link, useNavigate, useLocation, useParams } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { 
  LayoutDashboard, 
  BookOpen, 
  CalendarDays, 
  RefreshCcw, 
  MessageSquare, 
  LogOut,
  GraduationCap,
  PlusCircle
} from 'lucide-react'

export default function AppLayout({ children }) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const { examId, moduleId } = useParams()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  // Define navigation links based on context
  const examLinks = examId ? [
    { name: 'Dashboard', path: `/exams/${examId}/dashboard`, icon: LayoutDashboard },
    { name: 'Syllabus', path: `/exams/${examId}/syllabus`, icon: BookOpen },
    { name: 'Modules', path: `/exams/${examId}/modules`, icon: CalendarDays },
    { name: 'Revisions', path: `/exams/${examId}/revision-queue`, icon: RefreshCcw },
    { name: 'Feedback', path: `/exams/${examId}/feedback`, icon: MessageSquare },
  ] : []

  const globalLinks = [
    { name: 'My Exams', path: '/', icon: GraduationCap },
    { name: 'New Exam', path: '/exams/new', icon: PlusCircle },
  ]

  const linksToShow = examId ? examLinks : globalLinks

  return (
    <div className="flex h-screen overflow-hidden bg-cream font-sans">
      {/* Sidebar */}
      <aside className="w-64 bg-tan border-r-4 border-secondary flex flex-col flex-shrink-0 z-20 shadow-[6px_0px_0px_#541A1A]">
        {/* Logo Area */}
        <div className="h-16 flex items-center px-6 border-b-4 border-secondary bg-primary">
          <Link to="/" className="flex items-center gap-2.5 group">
            <div className="w-8 h-8 bg-cream border-2 border-secondary rounded flex items-center justify-center font-black text-secondary shadow-[2px_2px_0px_#541A1A] group-hover:translate-x-[1px] group-hover:translate-y-[1px] group-hover:shadow-[1px_1px_0px_#541A1A] transition-all">
              A
            </div>
            <span className="font-black text-xl text-cream tracking-tight uppercase">Ascendra</span>
          </Link>
        </div>

        {/* Navigation Links */}
        <nav className="flex-1 overflow-y-auto p-4 space-y-3">
          {examId && (
            <div className="mb-4 px-2 pt-2">
              <p className="text-xs font-black text-secondary/70 uppercase tracking-widest">Exam Tools</p>
            </div>
          )}
          {linksToShow.map((link) => {
            const Icon = link.icon
            // Active if exact match or if we are deeper in the route (e.g. /exams/1/modules/2 -> active on Modules)
            // But exclude '/' from prefix matching so 'My Exams' isn't always active
            const isActive = location.pathname === link.path || (link.path !== '/' && location.pathname.startsWith(link.path))
            
            return (
              <Link
                key={link.path}
                to={link.path}
                className={`flex items-center gap-3 px-3 py-3 rounded-xl border-2 font-bold transition-all ${
                  isActive 
                    ? 'bg-primary border-secondary text-cream shadow-[3px_3px_0px_#541A1A] translate-x-[-2px] translate-y-[-2px]' 
                    : 'bg-transparent border-transparent text-secondary hover:bg-cream hover:border-secondary hover:shadow-[3px_3px_0px_#541A1A] hover:translate-x-[-2px] hover:translate-y-[-2px]'
                }`}
              >
                <Icon size={20} strokeWidth={2.5} />
                <span className="tracking-wide">{link.name}</span>
              </Link>
            )
          })}
        </nav>

        {/* User Footer */}
        <div className="p-4 border-t-4 border-secondary bg-tan">
          <div className="flex items-center justify-between">
            <div className="flex flex-col">
              <span className="text-xs font-black text-secondary/70 uppercase tracking-wider">Logged In</span>
              <span className="text-sm font-bold text-secondary truncate max-w-[120px]">{user?.name}</span>
            </div>
            <button
              onClick={handleLogout}
              className="p-2 text-secondary hover:bg-red-400 hover:text-secondary rounded-lg border-2 border-transparent hover:border-secondary hover:shadow-[2px_2px_0px_#541A1A] transition-all"
              title="Sign out"
            >
              <LogOut size={20} strokeWidth={2.5} />
            </button>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 overflow-y-auto bg-cream relative">
        <div className="max-w-5xl mx-auto px-8 py-10 w-full">
          {children}
        </div>
      </main>
    </div>
  )
}
