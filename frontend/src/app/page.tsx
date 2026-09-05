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
            <PlaySquare size={16} className="text-red-500" />
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

        {/* Visual A/B Test Showcase */}
        <motion.div 
          initial={{ opacity: 0, y: 50 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 1, delay: 0.3 }}
          className="mt-24 relative max-w-5xl mx-auto"
        >
          <div className="absolute -inset-1 bg-gradient-to-r from-red-500 to-orange-500 rounded-[2.5rem] blur-2xl opacity-20" />
          <div className="relative bg-zinc-900/80 backdrop-blur-2xl border border-zinc-800 rounded-[2rem] p-4 md:p-8 shadow-2xl">
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 md:gap-12 relative">
              {/* Thumbnail A (Loser) */}
              <div className="relative group rounded-xl overflow-hidden border-2 border-zinc-800 bg-black">
                <div className="absolute top-4 left-4 bg-black/80 backdrop-blur-md px-3 py-1.5 rounded-full text-xs font-bold text-zinc-400 z-10 uppercase tracking-wider">
                  Original (A)
                </div>
                <img 
                  src="https://images.unsplash.com/photo-1616469829581-73993eb86b02?q=80&w=800&auto=format&fit=crop" 
                  alt="Boring Thumbnail"
                  className="w-full aspect-video object-cover opacity-60 grayscale-[40%] transition-transform duration-700 group-hover:scale-105"
                />
                <div className="absolute bottom-0 inset-x-0 p-5 bg-gradient-to-t from-black via-black/80 to-transparent">
                  <h3 className="text-lg font-bold text-white mb-2">How to build a PC</h3>
                  <div className="flex justify-between items-end">
                    <div>
                      <div className="text-[10px] text-zinc-500 uppercase font-bold mb-1">Click-Through Rate</div>
                      <div className="text-xl font-black text-zinc-300">4.2%</div>
                    </div>
                    <div className="text-right">
                      <div className="text-[10px] text-zinc-500 uppercase font-bold mb-1">Views</div>
                      <div className="text-sm font-bold text-zinc-400">12,450</div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Thumbnail B (Winner) */}
              <div className="relative group rounded-xl overflow-hidden border-2 border-red-500 shadow-[0_0_40px_rgba(239,68,68,0.2)] bg-black">
                <div className="absolute top-4 left-4 bg-red-600 px-4 py-1.5 rounded-full text-xs font-black text-white z-10 uppercase tracking-wider flex items-center gap-1.5 shadow-lg">
                  <Crown size={14} /> Winner (B)
                </div>
                <img 
                  src="https://images.unsplash.com/photo-1542751371-adc38448a05e?q=80&w=800&auto=format&fit=crop" 
                  alt="Exciting Thumbnail"
                  className="w-full aspect-video object-cover transition-transform duration-700 group-hover:scale-105"
                />
                <div className="absolute bottom-0 inset-x-0 p-5 bg-gradient-to-t from-black via-black/90 to-transparent">
                  <h3 className="text-xl font-black text-white mb-2 drop-shadow-md text-shadow-sm">
                    I BUILT THE ULTIMATE GAMING PC! 🤯
                  </h3>
                  <div className="flex justify-between items-end">
                    <div>
                      <div className="text-[10px] text-red-400/80 uppercase font-bold mb-1">Click-Through Rate</div>
                      <div className="text-3xl font-black text-red-400">{ctr}%</div>
                    </div>
                    <div className="text-right">
                      <div className="text-[10px] text-green-400/80 uppercase font-bold mb-1">Views</div>
                      <div className="text-lg font-black text-green-400 flex items-center gap-1">
                        <TrendingUp size={16} /> 89,200
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* VS Badge */}
              <div className="hidden md:flex absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-14 h-14 bg-zinc-950 border border-zinc-700 rounded-full items-center justify-center z-20 shadow-2xl">
                <span className="text-lg font-black italic text-zinc-500">VS</span>
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
          initial={{ opacity: 0, scale: 0.9 }}
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
