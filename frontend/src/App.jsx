import { BrowserRouter, Route, Routes } from "react-router-dom";
import ProtectedRoute from "./components/ProtectedRoute";
import { ToastProvider } from "./components/ui/Toast";
import { AuthProvider } from "./context/AuthContext";
import AiInsights from "./pages/AiInsights";
import Budget from "./pages/Budget";
import Categories from "./pages/Categories";
import Dashboard from "./pages/Dashboard";
import Home from "./pages/Home";
import Login from "./pages/Login";
import MonthComparison from "./pages/MonthComparison";
import FinancialHealth from "./pages/FinancialHealth";
import GoalPlanner from "./pages/GoalPlanner";
import MoneyLeaks from "./pages/MoneyLeaks";
import Register from "./pages/Register";
import Reports from "./pages/Reports";
import SmartAlerts from "./pages/SmartAlerts";
import Subscriptions from "./pages/Subscriptions";
import Transactions from "./pages/Transactions";
import Upload from "./pages/Upload";

/**
 * Wrap a route element in the authentication guard.
 */
function protectedElement(element) {
  return <ProtectedRoute>{element}</ProtectedRoute>;
}

/**
 * Render application routes for MoneyLeak AI.
 */
export default function App() {
  return (
    <AuthProvider>
      <ToastProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />
            <Route path="/upload" element={protectedElement(<Upload />)} />
            <Route path="/dashboard" element={protectedElement(<Dashboard />)} />
            <Route path="/month-comparison" element={protectedElement(<MonthComparison />)} />
            <Route path="/financial-health" element={protectedElement(<FinancialHealth />)} />
            <Route path="/goal-planner" element={protectedElement(<GoalPlanner />)} />
            <Route path="/transactions" element={protectedElement(<Transactions />)} />
            <Route path="/smart-alerts" element={protectedElement(<SmartAlerts />)} />
            <Route path="/categories" element={protectedElement(<Categories />)} />
            <Route path="/money-leaks" element={protectedElement(<MoneyLeaks />)} />
            <Route path="/subscriptions" element={protectedElement(<Subscriptions />)} />
            <Route path="/budget" element={protectedElement(<Budget />)} />
            <Route path="/reports" element={protectedElement(<Reports />)} />
            <Route path="/ai-insights" element={protectedElement(<AiInsights />)} />
          </Routes>
        </BrowserRouter>
      </ToastProvider>
    </AuthProvider>
  );
}
