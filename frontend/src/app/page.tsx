"use client";

import { motion } from "framer-motion";
import Link from "next/link";
import { PlaySquare, MousePointerClick, Crown, BarChart3, ArrowRight, Zap, PlayCircle, TrendingUp } from "lucide-react";
import { useEffect, useState } from "react";

export default function LandingPage() {
  const [ctr, setCtr] = useState(4.2);
  
  // CTR 올라가는 애니메이션 효과
  useEffect(() => {
    const timer = setTimeout(() => {
      const interval = setInterval(() => {
        setCtr(prev => {
          if (prev >= 11.8) {
            clearInterval(interval);
            return 11.8;
          }
          return +(prev + 0.2).toFixed(1);
        });
      }, 40);
      return () => clearInterval(interval);
    }, 1000);
    return () => clearTimeout(timer);
  }, []);

  return (
    <div className="min-h-screen bg-[#050505] text-zinc-100 selection:bg-red-500/30 overflow-x-hidden">
      {/* Background Gradients */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[1000px] h-[500px] bg-red-600/10 blur-[120px] rounded-full pointer-events-none" />
      
      {/* Hero Section */}
      <section className="relative pt-32 pb-20 px-6 max-w-7xl mx-auto text-center z-10">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, ease: "easeOut" }}
        >
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-zinc-900 border border-zinc-800 text-sm font-medium text-zinc-300 mb-8 shadow-xl">
            <Youtube size={16} className="text-red-500" />
            <span>The Most Guaranteed Way to Beat the YouTube Algorithm</span>
          </div>
          
          <h1 className="text-5xl md:text-7xl font-black tracking-tight mb-8 leading-[1.1]">
            One Thumbnail <br className="hidden md:block" />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-red-500 via-orange-500 to-yellow-500">
              Decides Your Video's Fate.
            </span>
          </h1>
          
          <p className="text-lg md:text-xl text-zinc-400 max-w-2xl mx-auto mb-12 leading-relaxed">
            Stop relying on gut feelings. Just upload your variants, <br className="hidden md:block" />
            and our system will automatically test them to find the highest CTR winner.
          </p>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link 
              href="/login" 
              className="group relative flex items-center gap-2 px-8 py-4 bg-white text-black font-black text-lg rounded-full overflow-hidden transition-transform hover:scale-105 active:scale-95"
            >
              <div className="absolute inset-0 w-full h-full bg-gradient-to-r from-zinc-200 to-white opacity-0 group-hover:opacity-100 transition-opacity" />
              <span className="relative z-10">Start Optimizing for Free</span>
              <ArrowRight size={20} className="relative z-10 group-hover:translate-x-1 transition-transform" />
            </Link>
          </div>
        </motion.div>

        {/* Visual A/B Test Showcase (Authentic YouTube UI) */}
        <motion.div 
          initial={{ opacity: 0, y: 50 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 1, delay: 0.3 }}
          className="mt-24 relative max-w-5xl mx-auto"
        >
          <div className="absolute -inset-1 bg-gradient-to-r from-red-500 to-orange-500 rounded-[2.5rem] blur-2xl opacity-20" />
          <div className="relative bg-zinc-900/80 backdrop-blur-2xl border border-zinc-800 rounded-[2rem] p-6 md:p-10 shadow-2xl">
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-8 md:gap-16 relative">
              
              {/* Thumbnail A (Loser) */}
              <div className="relative group rounded-2xl border-2 border-zinc-800 bg-[#0f0f0f] p-4 md:p-5 flex flex-col">
                {/* Platform Meta (CTR, Status) */}
                <div className="flex justify-between items-center mb-5">
                   <span className="bg-zinc-800 text-zinc-300 text-xs font-bold px-3 py-1.5 rounded-full uppercase tracking-wider">Original (A)</span>
                   <div className="text-right">
                     <div className="text-[10px] text-zinc-500 uppercase font-bold">Current CTR</div>
                     <div className="text-xl font-black text-zinc-400">4.2%</div>
                   </div>
                </div>

                {/* Actual YouTube Card Mockup */}
                <div className="flex flex-col cursor-pointer">
                  <div className="relative rounded-xl overflow-hidden aspect-video">
                     <img src="https://images.unsplash.com/photo-1616469829581-73993eb86b02?q=80&w=800&auto=format&fit=crop" alt="Thumbnail A" className="w-full h-full object-cover opacity-80 grayscale-[30%]" />
                     {/* Time Badge */}
                     <div className="absolute bottom-1.5 right-1.5 bg-black/90 text-white text-xs font-medium px-1.5 py-0.5 rounded">
                       12:45
                     </div>
                  </div>
                  <div className="flex gap-3 mt-3">
                    <div className="w-9 h-9 rounded-full bg-zinc-800 flex-shrink-0 mt-0.5">
                       <img src="https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?q=80&w=100&auto=format&fit=crop" alt="Avatar" className="w-full h-full rounded-full object-cover opacity-80" />
                    </div>
                    <div className="flex flex-col text-left">
                      <h3 className="text-zinc-300 text-[15px] font-semibold leading-tight line-clamp-2">How to build a PC (Step by Step Guide)</h3>
                      <span className="text-zinc-500 text-[13px] mt-1">CreatorFlow Tech</span>
                      <span className="text-zinc-500 text-[13px]">12K views • 3 hours ago</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Thumbnail B (Winner) */}
              <div className="relative group rounded-2xl border-2 border-red-500 bg-[#0f0f0f] p-4 md:p-5 flex flex-col shadow-[0_0_30px_rgba(239,68,68,0.15)] overflow-hidden">
                <div className="absolute inset-0 bg-red-500/5 pointer-events-none" />
                
                {/* Platform Meta (CTR, Status) */}
                <div className="flex justify-between items-center mb-5 relative z-10">
                   <span className="bg-red-600 text-white text-xs font-black px-3 py-1.5 rounded-full flex items-center gap-1.5 uppercase tracking-wider shadow-lg"><Crown size={14}/> Winner (B)</span>
                   <div className="text-right">
                     <div className="text-[10px] text-red-400 uppercase font-bold flex items-center justify-end gap-1"><TrendingUp size={12}/> Live CTR</div>
                     <div className="text-3xl font-black text-red-500">{ctr}%</div>
                   </div>
                </div>

                {/* Actual YouTube Card Mockup */}
                <div className="flex flex-col cursor-pointer relative z-10">
                  <div className="relative rounded-xl overflow-hidden aspect-video">
                     <img src="https://images.unsplash.com/photo-1542751371-adc38448a05e?q=80&w=800&auto=format&fit=crop" alt="Thumbnail B" className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105" />
                     {/* Time Badge */}
                     <div className="absolute bottom-1.5 right-1.5 bg-black/90 text-white text-xs font-medium px-1.5 py-0.5 rounded">
                       12:45
                     </div>
                  </div>
                  <div className="flex gap-3 mt-3">
                    <div className="w-9 h-9 rounded-full bg-zinc-800 flex-shrink-0 mt-0.5">
                       <img src="https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?q=80&w=100&auto=format&fit=crop" alt="Avatar" className="w-full h-full rounded-full object-cover" />
                    </div>
                    <div className="flex flex-col text-left">
                      <h3 className="text-white text-[15px] font-semibold leading-tight line-clamp-2">I BUILT THE ULTIMATE GAMING PC! 🤯</h3>
                      <span className="text-zinc-400 text-[13px] mt-1">CreatorFlow Tech</span>
                      <span className="text-zinc-400 text-[13px]">89K views • 3 hours ago</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* VS Badge */}
              <div className="hidden md:flex absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-16 h-16 bg-zinc-950 border-2 border-zinc-700 rounded-full items-center justify-center z-20 shadow-2xl">
                <span className="text-xl font-black italic text-zinc-500">VS</span>
              </div>
            </div>

          </div>
        </motion.div>
      </section>

      {/* Process Section */}
      <section className="py-32 bg-zinc-950 border-t border-zinc-900 relative z-10">
        <div className="max-w-7xl mx-auto px-6">
          <div className="text-center mb-20">
            <h2 className="text-3xl md:text-5xl font-black mb-6">You Focus on Creating.</h2>
            <p className="text-zinc-400 text-lg">We handle the complex A/B testing and data analysis automatically.</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            <FeatureCard 
              delay={0.1}
              icon={<MousePointerClick size={32} className="text-blue-400" />}
              title="1. Upload Variants"
              desc="Upload multiple thumbnails and titles. Setup takes less than 60 seconds."
            />
            <FeatureCard 
              delay={0.2}
              icon={<Zap size={32} className="text-yellow-400" />}
              title="2. Real-time Hourly Swaps"
              desc="We automatically rotate your thumbnails and track viewer engagement in real-time."
            />
            <FeatureCard 
              delay={0.3}
              icon={<BarChart3 size={32} className="text-emerald-400" />}
              title="3. Crown the Winner"
              desc="The thumbnail with the highest CTR is permanently applied to maximize your views."
            />
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-32 relative overflow-hidden text-center z-10">
        <div className="absolute inset-0 bg-gradient-to-b from-transparent to-red-950/20 pointer-events-none" />
        <motion.div
          initial={{ opacity: 0, y: 0.9 }}
          whileInView={{ opacity: 1, scale: 1 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="max-w-4xl mx-auto px-6 relative z-10"
        >
          <PlayCircle size={64} className="mx-auto text-red-500 mb-8 opacity-80" />
          <h2 className="text-4xl md:text-6xl font-black text-white mb-8">
            Ready to Explode Your Views?
          </h2>
          <p className="text-xl text-zinc-400 mb-10">
            Stop guessing. Start testing. Let the data decide your next viral hit.
          </p>
          <Link href="/login" className="inline-flex px-12 py-5 bg-red-600 text-white hover:bg-red-500 rounded-full font-black text-xl transition-all hover:scale-105 active:scale-95 shadow-[0_0_40px_rgba(239,68,68,0.4)]">
            Get Started for Free
          </Link>
        </motion.div>
      </section>

      {/* Footer */}
      <footer className="py-8 text-center border-t border-zinc-900 text-zinc-600 text-sm bg-zinc-950 relative z-10">
        <p>© 2026 CREATORFLOW. All rights reserved.</p>
      </footer>
    </div>
  );
}

function FeatureCard({ icon, title, desc, delay }: { icon: React.ReactNode, title: string, desc: string, delay: number }) {
  return (
    <motion.div 
      initial={{ opacity: 0, y: 30 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-50px" }}
      transition={{ duration: 0.6, delay }}
      className="p-10 rounded-[2rem] bg-zinc-900/50 border border-zinc-800/50 hover:bg-zinc-900 transition-colors group relative overflow-hidden"
    >
      <div className="absolute top-0 right-0 p-8 opacity-[0.03] group-hover:opacity-[0.05] transition-opacity duration-500 transform group-hover:scale-110 group-hover:rotate-12">
        {icon}
      </div>
      <div className="w-16 h-16 rounded-2xl bg-zinc-950 border border-zinc-800 flex items-center justify-center mb-8 shadow-xl relative z-10">
        {icon}
      </div>
      <h3 className="text-2xl font-bold text-white mb-4 relative z-10">{title}</h3>
      <p className="text-zinc-400 leading-relaxed text-lg relative z-10">{desc}</p>
    </motion.div>
  );
}
