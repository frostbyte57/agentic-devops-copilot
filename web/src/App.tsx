import { createBrowserRouter, RouterProvider } from "react-router-dom";

import { Toaster } from "@/components/ui/sonner";
import Home from "@/routes/home";

const router = createBrowserRouter([
  {
    path: "/",
    element: <Home />,
  },
]);

export default function App() {
  return (
    <>
      <RouterProvider router={router} />
      <Toaster />
    </>
  );
}
