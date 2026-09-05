"use client";

import React from "react";
import { AlertCircle, CheckCircle2, Info, AlertTriangle, X, Loader2 } from "lucide-react";

export interface ModalProps {
  isOpen: boolean;
  type?: "alert" | "confirm" | "loading";
  variant?: "info" | "success" | "warning" | "error";
  title: string;
  message: string;
  confirmText?: string;
  cancelText?: string;
  onConfirm: () => void;
  onCancel?: () => void;
}

export default function Modal({
  isOpen,
  type = "alert",
  variant = "info",
  title,
  message,
  confirmText = "확인",
  cancelText = "취소",
  onConfirm,
  onCancel,
}: ModalProps) {
  const handleClose = () => {
    if (type === "loading") return; // Prevent closing while loading
    if (onCancel) {
      onCancel();
    } else if (type === "alert") {
      onConfirm(); // For alerts, onConfirm acts as the close action
    }
  };

  React.useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        handleClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, type, onConfirm, onCancel]);

  if (!isOpen) return null;

  const getIcon = () => {
    if (type === "loading") {
      return <Loader2 className="w-8 h-8 text-cyan-400 animate-spin" aria-hidden="true" />;
    }
    switch (variant) {
      case "success":
        return <CheckCircle2 className="w-8 h-8 text-emerald-400" aria-hidden="true" />;
      case "warning":
        return <AlertTriangle className="w-8 h-8 text-amber-400" aria-hidden="true" />;
      case "error":
        return <AlertCircle className="w-8 h-8 text-rose-400" aria-hidden="true" />;
      default:
        return <Info className="w-8 h-8 text-cyan-400" aria-hidden="true" />;
    }
  };

  const getBorderGlow = () => {
    switch (variant) {
      case "success":
        return "border-emerald-500/30 shadow-[0_0_30px_rgba(16,185,129,0.15)]";
      case "warning":
        return "border-amber-500/30 shadow-[0_0_30px_rgba(245,158,11,0.15)]";
      case "error":
        return "border-rose-500/30 shadow-[0_0_30px_rgba(244,63,94,0.15)]";
      default:
        return "border-cyan-500/30 shadow-[0_0_30px_rgba(6,182,212,0.15)]";
    }
  };

  const getButtonBg = () => {
    switch (variant) {
      case "success":
        return "bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 focus-visible:ring-emerald-400";
      case "warning":
        return "bg-gradient-to-r from-amber-600 to-orange-600 hover:from-amber-500 hover:to-orange-500 focus-visible:ring-amber-400";
      case "error":
        return "bg-gradient-to-r from-rose-600 to-red-600 hover:from-rose-500 hover:to-red-500 focus-visible:ring-rose-400";
      default:
        return "bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 focus-visible:ring-cyan-400";
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="modal-title"
      aria-describedby="modal-description"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-md animate-in fade-in duration-200"
    >
      <div className={`relative w-full max-w-md bg-[#0f0f12]/90 border rounded-2xl p-6 text-zinc-100 backdrop-blur-xl transition-all scale-100 ${getBorderGlow()}`}>
        {type !== "loading" && (
          <button
            onClick={handleClose}
            aria-label="모달 닫기"
            className="absolute top-4 right-4 text-zinc-400 hover:text-zinc-200 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 rounded-lg p-1"
          >
            <X size={18} aria-hidden="true" />
          </button>
        )}

        {/* Content */}
        <div className="flex items-start gap-4">
          <div className="p-2.5 rounded-xl bg-zinc-900/80 border border-zinc-800 flex-shrink-0">
            {getIcon()}
          </div>
          <div className="flex-1 pr-4">
            <h3 id="modal-title" className="text-lg font-bold text-zinc-100 tracking-tight mb-1">{title}</h3>
            <p id="modal-description" className="text-sm text-zinc-300 leading-relaxed whitespace-pre-line">{message}</p>
          </div>
        </div>

        {/* Actions */}
        {type !== "loading" && (
          <div className="flex items-center justify-end gap-3 mt-6 pt-4 border-t border-zinc-800/60">
            {type === "confirm" && (
              <button
                onClick={onCancel}
                className="px-5 py-2.5 text-sm font-bold text-zinc-200 hover:text-white bg-zinc-800 hover:bg-zinc-700 border border-zinc-600 rounded-xl transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zinc-400"
              >
                {cancelText}
              </button>
            )}
            <button
              onClick={onConfirm}
              className={`px-5 py-2.5 text-sm font-bold text-white rounded-xl shadow-lg transition-all active:scale-95 focus-visible:outline-none focus-visible:ring-2 ${getButtonBg()}`}
            >
              {confirmText}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
