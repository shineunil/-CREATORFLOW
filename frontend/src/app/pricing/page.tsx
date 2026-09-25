"use client";

import React, { useState, useEffect, useRef } from "react";
import { Check, Crown, Zap, CreditCard, Sparkles, ShieldCheck, X, Loader2 } from "lucide-react";
import Modal from "@/components/Modal";
import { apiFetch } from "@/lib/api";
import { openPaddleCheckout } from "@/lib/paddle";
import { useI18n } from "@/i18n/I18nProvider";
import RichText from "@/i18n/RichText";

export default function PricingPage() {
  const { t, locale } = useI18n();
  const P = t.pricingApp;
  const [isCheckoutModalOpen, setIsCheckoutModalOpen] = useState(false);
  const [isRedirecting, setIsRedirecting] = useState(false);
  const [userProfile, setUserProfile] = useState<{ email?: string; channel_title?: string; plan: string; is_pro: boolean }>({ plan: "BASIC", is_pro: false });
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

  const handlePaddleCheckout = async () => {
    setIsRedirecting(true);
    try {
      await openPaddleCheckout(locale);
      setIsCheckoutModalOpen(false);
    } catch (err: any) {
      console.error("Paddle Checkout Error:", err);
      setIsCheckoutModalOpen(false);
      showAlert(P.errorTitle, err.message || t.checkout.failed, "error");
    } finally {
      setIsRedirecting(false);
    }
  };

  return (
    <>
      <div className="p-8 max-w-5xl mx-auto animate-fade-in-up">
        <div className="text-center mb-16">
          <h1 className="text-4xl font-black mb-4">{P.title}</h1>
          <p className="text-zinc-400 text-lg">{P.sub}</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 max-w-4xl mx-auto">
          {/* Basic Plan */}
          <div className="glass-panel rounded-3xl p-8 border border-zinc-800/50 flex flex-col">
            <h3 className="text-2xl font-bold mb-2">{P.basicName}</h3>
            <p className="text-zinc-400 text-sm mb-6 h-10">{t.plans.basicDesc}</p>
            <div className="mb-8">
              <span className="text-4xl font-bold">$0</span>
              <span className="text-zinc-400"> {t.common.perMonth}</span>
            </div>

            <ul className="space-y-4 mb-10 flex-1">
              {P.basicFeatures.map((feature) => (
                <li key={feature} className="flex items-center gap-3 text-sm text-zinc-300">
                  <Check size={18} className="text-zinc-400 flex-shrink-0" aria-hidden="true" />
                  {feature}
                </li>
              ))}
            </ul>

            <button disabled className="w-full py-4 rounded-xl bg-zinc-900 text-zinc-400 font-bold border border-zinc-800 cursor-not-allowed">
              {userProfile.is_pro ? P.freePlan : P.currentPlan}
            </button>
          </div>

          {/* Pro Plan */}
          <div className="glass-panel rounded-3xl p-8 border border-cyan-500/50 flex flex-col relative overflow-hidden transition-transform hover:scale-105 duration-300 shadow-[0_0_40px_rgba(6,182,212,0.15)]">
            <div className="absolute top-0 right-0 bg-gradient-to-r from-cyan-500 to-blue-500 text-white text-xs font-bold px-4 py-1.5 rounded-bl-xl uppercase tracking-wider flex items-center gap-1">
              <Zap size={14} fill="currentColor" aria-hidden="true" /> {t.plans.mostPopular}
            </div>

            <h3 className="text-2xl font-bold mb-2 flex items-center gap-2 text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-blue-400">
              <Crown size={24} className="text-cyan-400" aria-hidden="true" />
              {t.plans.proName}
            </h3>
            <p className="text-zinc-400 text-sm mb-6 h-10">{t.plans.proDesc}</p>
            <div className="mb-8">
              <span className="text-4xl font-bold">$29</span>
              <span className="text-zinc-400"> {t.common.perMonth}</span>
            </div>

            <ul className="space-y-4 mb-10 flex-1">
              <ProFeature><RichText value={t.plans.proFeatures.testsPerMonth} strongClassName="font-semibold text-cyan-300" /></ProFeature>
              <ProFeature><RichText value={t.plans.proFeatures.concurrent} strongClassName="font-semibold text-cyan-300" /></ProFeature>
              <ProFeature>{P.proVariants}</ProFeature>
              <ProFeature><RichText value={P.proInterval} strongClassName="font-semibold text-cyan-300" /></ProFeature>
              <ProFeature>{t.plans.proFeatures.autoApply}</ProFeature>
              <ProFeature><RichText value={t.plans.proFeatures.email} strongClassName="font-semibold text-cyan-300" /></ProFeature>
            </ul>

            {userProfile.is_pro ? (
              <div className="w-full py-4 rounded-xl bg-gradient-to-r from-emerald-600/30 to-teal-600/30 border border-emerald-500/50 text-emerald-400 font-bold flex items-center justify-center gap-2 shadow-lg">
                <ShieldCheck size={20} aria-hidden="true" />
                <span>{P.proActive}</span>
              </div>
            ) : (
              <button
                ref={upgradeButtonRef}
                onClick={() => setIsCheckoutModalOpen(true)}
                className="w-full py-4 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white font-extrabold transition-all shadow-lg hover:shadow-cyan-500/25 flex items-center justify-center gap-2 cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950"
              >
                <CreditCard size={18} aria-hidden="true" />
                <span>{P.upgrade}</span>
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Checkout Confirmation Modal */}
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
                  <Sparkles size={14} aria-hidden="true" /> {P.secureCheckout}
                </span>
                <h3 id="checkout-modal-title" className="text-2xl font-extrabold mt-1">{P.checkoutTitle}</h3>
              </div>
              <button
                onClick={() => { if (!isRedirecting) { setIsCheckoutModalOpen(false); upgradeButtonRef.current?.focus(); } }}
                aria-label={P.closeCheckout}
                disabled={isRedirecting}
                className="text-zinc-400 hover:text-white p-1 cursor-pointer rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 disabled:opacity-50"
              >
                <X size={20} aria-hidden="true" />
              </button>
            </div>

            <div className="bg-zinc-900/80 border border-zinc-800 rounded-2xl p-4 space-y-3">
              <div className="flex justify-between text-sm">
                <span className="text-zinc-400">{P.planLabel}</span>
                <span className="font-bold text-white">{P.planValue}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-zinc-400">{P.amountLabel}</span>
                <span className="font-bold text-emerald-400 text-base">{P.amountValue}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-zinc-400">{P.billingLabel}</span>
                <span className="text-zinc-300">{P.billingValue}</span>
              </div>
            </div>

            <div className="space-y-3">
              <button
                onClick={handlePaddleCheckout}
                disabled={isRedirecting}
                className="w-full py-3.5 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 disabled:from-zinc-700 disabled:to-zinc-700 disabled:cursor-not-allowed text-white font-extrabold transition-all shadow-lg hover:shadow-cyan-500/25 flex items-center justify-center gap-2 cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950"
              >
                {isRedirecting ? (
                  <>
                    <Loader2 size={18} className="animate-spin" aria-hidden="true" />
                    <span>{t.checkout.opening}</span>
                  </>
                ) : (
                  <>
                    <CreditCard size={18} aria-hidden="true" />
                    <span>{P.proceed}</span>
                  </>
                )}
              </button>
            </div>
            <p className="text-[11px] text-center text-zinc-400">
              {P.footnote}
            </p>
          </div>
        </div>
      )}

      <Modal {...modalConfig} />
    </>
  );
}

function ProFeature({ children }: { children: React.ReactNode }) {
  return (
    <li className="flex items-center gap-3 text-sm text-zinc-100">
      <Check size={18} className="text-cyan-400 flex-shrink-0" aria-hidden="true" />
      <span>{children}</span>
    </li>
  );
}
