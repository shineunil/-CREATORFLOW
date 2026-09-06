"use client";

import React from "react";
import Link from "next/link";
import { FlaskConical, PlaySquare, ArrowLeft } from "lucide-react";

export default function LoginPage() {
  const handleGoogleLogin = () => {
    window.location.href = "https://creatorflow-sff9-o4brraeeo-eimo.vercel.app/api/auth/login";
  };

  return (
    <div className="relative min-h-screen bg-[#09090b] flex items-center justify-center p-4 overflow-hidden font-sans">
      {/* Background Effects */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-cyan-900/20 rounded-full blur-[150px] pointer-events-none" />
      <div className="absolute top-1/2 left-1/4 -translate-y-1/2 w-[400px] h-[400px] bg-violet-900/20 rounded-full blur-[120px] pointer-events-none" />

      {/* Back to Home */}
      <Link href="/" className="absolute top-8 left-8 text-zinc-400 hover:text-white flex items-center gap-2 transition-colors font-medium">
        <ArrowLeft size={20} />
        Back to Home
      </Link>

      <div className="relative z-10 w-full max-w-md">
        {/* Logo */}
        <div className="flex flex-col items-center mb-10">
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-cyan-500 via-blue-500 to-violet-600 flex items-center justify-center text-white shadow-lg shadow-cyan-500/20 border border-cyan-400/30 mb-6">
            <FlaskConical size={32} />
          </div>
          <h1 className="text-3xl font-black text-white tracking-tight mb-2">Welcome Back</h1>
          <p className="text-zinc-400 text-center text-sm">
            Sign in and connect your YouTube channel to start optimizing your thumbnails.
          </p>
        </div>

        {/* Login Card */}
        <div className="glass-panel p-8 rounded-3xl border border-zinc-800/80 bg-zinc-900/40 backdrop-blur-xl shadow-2xl">
          <button 
            onClick={handleGoogleLogin}
            className="w-full flex items-center justify-center gap-3 px-6 py-4 bg-white hover:bg-zinc-200 text-black rounded-xl font-bold transition-all hover:scale-[1.02] active:scale-[0.98] shadow-[0_0_20px_rgba(255,255,255,0.1)] cursor-pointer"
          >
            {/* Google G Logo SVG */}
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
              <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
              <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
              <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
            </svg>
            Continue with Google
          </button>

          <div className="mt-6 flex items-center justify-between text-xs text-zinc-500">
            <div className="flex-1 h-px bg-zinc-800" />
            <span className="px-4">OR</span>
            <div className="flex-1 h-px bg-zinc-800" />
          </div>

          <button 
            onClick={handleGoogleLogin}
            className="w-full mt-6 flex items-center justify-center gap-3 px-6 py-4 bg-zinc-800 hover:bg-zinc-700 text-white border border-zinc-700 rounded-xl font-bold transition-all hover:scale-[1.02] active:scale-[0.98] cursor-pointer"
          >
            <PlaySquare size={20} className="text-red-500" />
            Connect YouTube Directly
          </button>

          <p className="mt-8 text-center text-xs text-zinc-600 leading-relaxed">
            By signing in, you agree to our <a href="#" className="text-cyan-500 hover:underline">Terms of Service</a> and <a href="#" className="text-cyan-500 hover:underline">Privacy Policy</a>.
          </p>
        </div>
      </div>
    </div>
  );
}
