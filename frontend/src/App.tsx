import {Routes,Route} from "react-router-dom";import Workspace from "./pages/Workspace";import OnePagerPage from "./pages/OnePagerPage";
export default function App(){return <Routes><Route path="/" element={<Workspace/>}/><Route path="/one-pagers/:id" element={<OnePagerPage/>}/></Routes>}
