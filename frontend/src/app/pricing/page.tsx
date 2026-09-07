"use client";

import React, { useState, useEffect, useRef } from "react";
import { Check, Crown, Zap, CreditCard, Sparkles, ShieldCheck, X } from "lucide-react";
import Modal from "@/components/Modal";
import { apiFetch } from "@/lib/api";
import { PADDLE_CONFIG } from "@/lib/config";

import { initializePaddle, Paddle } from '@paddle/paddle-js';

export default function PricingPage() {
  const [isCheckoutModalOpen, setIsCheckoutModalOpen] = useState(false);
  const [userProfile, setUserProfile] = useState<{ email?: string; channel_title?: string; plan: string; is_pro: boolean }>({ plan: "BASIC", is_pro: false });
  const [paddle, setPaddle] = useState<Paddle>();
  const upgradeButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!isCheckoutModalOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setIsCheckoutModalOpen(false);
        upgradeButtonRef.current?.focus();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isCheckoutModalOpen]);

  useEffect(() => {
    initializePaddle({ 
      environment: PADDLE_CONFIG.environment, 
      token: PADDLE_CONFIG.clientToken,
      eventCallback: async function(data) {
        if (data.name === "checkout.completed") {
          setIsCheckoutModalOpen(false);
          showAlert(
            "🚀 PRO Plan Upgraded!",
            "Payment successful! Welcome to CreatorFlow PRO.\nYour account will be upgraded shortly.",
            "success",
            () => {
              window.location.href = "/dashboard";
            }
          );
        }
      }
    }).then(
      (paddleInstance: Paddle | undefined) => {
        if (paddleInstance) {
          setPaddle(paddleInstance);
        }
      },
    );
  }, []);

  // Modal State
  const [modalConfig, setModalConfig] = useState<{
    isOpen: boolean;
    type?: "alert" | "confirm";
    variant?: "info" | "success" | "warning" | "error";
    title: string;
    message: string;
    onConfirm: () => void;
  }>({
    isOpen: false,
    title: "",
    message: "",
    onConfirm: () => {},
  });

  const showAlert = (title: string, message: string, variant: "info" | "success" | "warning" | "error" = "info", onConfirm?: () => void) => {
    setModalConfig({
      isOpen: true,
      type: "alert",
      variant,
      title,
      message,
      onConfirm: () => {
        setModalConfig(prev => ({ ...prev, isOpen: false }));
        if (onConfirm) onConfirm();
      }
    });
  };

  const fetchUserProfile = () => {
    apiFetch("/api/user/me")
      .then(res => {
        if (!res.ok) throw new Error(`Failed to load profile (${res.status})`);
        return res.json();
      })
      .then(data => {
        setUserProfile(data);
      })
      .catch(err => console.error(err));
  };

  useEffect(() => {
    fetchUserProfile();
  }, []);

  const handleStartCheckout = () => {
    setIsCheckoutModalOpen(true);
  };


  const handlePaddleCheckout = () => {
    if (!paddle) {
      showAlert("Notice", "Payment gateway is initializing. Please try again in a moment.", "warning");
      return;
    }
    
    setIsCheckoutModalOpen(false);
    const checkoutOptions: any = {
      items: [
        {
          priceId: PADDLE_CONFIG.proPriceId,
          quantity: 1
        }
      ]
    };

    try {
      paddle.Checkout.open(checkoutOptions);
    } catch(err) {
      console.error("Paddle Checkout Error:", err);
    }
  };

  return (
    <>
      <div className="p-8 max-w-5xl mx-auto animate-fade-in-up">
        <div className="text-center mb-16">
          <h1 className="text-4xl font-black mb-4">Pricing Plans</h1>
          <p className="text-zinc-400 text-lg">Choose the best plan for your channel growth.</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 max-w-4xl mx-auto">
          {/* Basic Plan */}
          <div className="glass-panel rounded-3xl p-8 border border-zinc-800/50 flex flex-col">
            <h3 className="text-2xl font-bold mb-2">BASIC (Free)</h3>
            <p className="text-zinc-400 text-sm mb-6 h-10">For creators who want to try the service</p>
            <div className="mb-8">
              <span className="text-4xl font-bold">$0</span>
              <span className="text-zinc-400"> / month</span>
            </div>

            <ul className="space-y-4 mb-10 flex-1">
              <li className="flex items-center gap-3 text-sm text-zinc-300">
                <Check size={18} className="text-zinc-400 flex-shrink-0" aria-hidden="true" />
                Max 4 tests per month
              </li>
              <li className="flex items-center gap-3 text-sm text-zinc-300">
                <Check size={18} className="text-zinc-400 flex-shrink-0" aria-hidden="true" />
                Max 1 concurrent test
              </li>
              <li className="flex items-center gap-3 text-sm text-zinc-300">
                <Check size={18} className="text-zinc-400 flex-shrink-0" aria-hidden="true" />
                Max 2 extra thumbnails (A, B, C)
              </li>
              <li className="flex items-center gap-3 text-sm text-zinc-300">
                <Check size={18} className="text-zinc-400 flex-shrink-0" aria-hidden="true" />
                Minimum swap interval: 4 hours
              </li>
            </ul>

            <button disabled className="w-full py-4 rounded-xl bg-zinc-900 text-zinc-400 font-bold border border-zinc-800 cursor-not-allowed">
              {userProfile.is_pro ? "Free Plan" : "Current Plan"}
            </button>
          </div>

          {/* Pro Plan */}
          <div className="glass-panel rounded-3xl p-8 border border-cyan-500/50 flex flex-col relative overflow-hidden transition-transform hover:scale-105 duration-300 shadow-[0_0_40px_rgba(6,182,212,0.15)]">
            <div className="absolute top-0 right-0 bg-gradient-to-r from-cyan-500 to-blue-500 text-white text-xs font-bold px-4 py-1.5 rounded-bl-xl uppercase tracking-wider flex items-center gap-1">
              <Zap size={14} fill="currentColor" aria-hidden="true" /> Most Popular
            </div>

            <h3 className="text-2xl font-bold mb-2 flex items-center gap-2 text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-blue-400">
              <Crown size={24} className="text-cyan-400" aria-hidden="true" />
              PRO Premium
            </h3>
            <p className="text-zinc-400 text-sm mb-6 h-10">For serious creators who want to maximize views</p>
            <div className="mb-8">
              <span className="text-4xl font-bold">$29</span>
              <span className="text-zinc-400"> / month</span>
            </div>

            <ul className="space-y-4 mb-10 flex-1">
              <li className="flex items-center gap-3 text-sm text-zinc-100">
                <Check size={18} className="text-cyan-400 flex-shrink-0" aria-hidden="true" />
                <span className="font-semibold text-cyan-300">Unlimited</span> tests per month
              </li>
              <li className="flex items-center gap-3 text-sm text-zinc-100">
                <Check size={18} className="text-cyan-400 flex-shrink-0" aria-hidden="true" />
                <span className="font-semibold text-cyan-300">Unlimited</span> concurrent tests
              </li>
              <li className="flex items-center gap-3 text-sm text-zinc-100">
                <Check size={18} className="text-cyan-400 flex-shrink-0" aria-hidden="true" />
                Max 4 extra thumbnails (A~E)
              </li>
              <li className="flex items-center gap-3 text-sm text-zinc-100">
                <Check size={18} className="text-cyan-400 flex-shrink-0" aria-hidden="true" />
                <span className="font-semibold text-cyan-300">Ultra-fast 30 mins</span> swap interval
              </li>
              </ul>

            {userProfile.is_pro ? (
              <div className="w-full py-4 rounded-xl bg-gradient-to-r from-emerald-600/30 to-teal-600/30 border border-emerald-500/50 text-emerald-400 font-bold flex items-center justify-center gap-2 shadow-lg">
                <ShieldCheck size={20} aria-hidden="true" />
                <span>Currently on PRO (Unlimited Active)</span>
              </div>
            ) : (
              <button
                ref={upgradeButtonRef}
                onClick={handleStartCheckout}
                aria-haspopup="dialog"
                className="w-full py-4 rounded-xl bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white font-bold transition-all shadow-lg hover:shadow-cyan-500/25 cursor-pointer flex items-center justify-center gap-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-900"
              >
                <CreditCard size={18} aria-hidden="true" />
                <span>Upgrade to PRO</span>
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Payment Gateway Modal */}
      {isCheckoutModalOpen && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="checkout-modal-title"
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-fade-in"
        >
          <div className="bg-zinc-950 border border-cyan-500/40 rounded-3xl p-6 md:p-8 max-w-lg w-full shadow-[0_0_50px_rgba(6,182,212,0.25)] space-y-6 relative overflow-hidden">
            <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-cyan-500 via-blue-500 to-violet-500" aria-hidden="true" />

            <div className="flex justify-between items-start">
              <div>
                <span className="text-xs font-bold uppercase tracking-wider text-cyan-400 flex items-center gap-1">
                  <Sparkles size={14} aria-hidden="true" /> Paddle Global Payment
                </span>
                <h3 id="checkout-modal-title" className="text-2xl font-extrabold mt-1">PRO Premium Checkout</h3>
              </div>
              <button
                onClick={() => { setIsCheckoutModalOpen(false); upgradeButtonRef.current?.focus(); }}
                aria-label="결제 창 닫기"
                className="text-zinc-400 hover:text-white p-1 cursor-pointer rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400"
              >
                <X size={20} aria-hidden="true" />
              </button>
            </div>

            <div className="bg-zinc-900/80 border border-zinc-800 rounded-2xl p-4 space-y-3">
              <div className="flex justify-between text-sm">
                <span className="text-zinc-400">Subscription Plan</span>
                <span className="font-bold text-white">PRO Premium (Monthly)</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-zinc-400">Total Amount</span>
                <span className="font-bold text-emerald-400 text-base">$29.00 / month</span>
              </div>
            </div>

            <div className="space-y-3">
              <button onClick={handlePaddleCheckout} className="w-full py-3.5 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white font-extrabold transition-all shadow-lg hover:shadow-cyan-500/25 flex items-center justify-center gap-2 cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950">
                <CreditCard size={18} aria-hidden="true" />
                <span>Proceed with Paddle Checkout</span>
              </button>
            </div>
            <p className="text-[11px] text-center text-zinc-400">
              Paddle acts as the Merchant of Record (MoR) for secure global payments.
            </p>
          </div>
        </div>
      )}

      <Modal {...modalConfig} />
    </>
  );
}
