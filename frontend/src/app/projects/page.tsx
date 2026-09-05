import React from 'react';
import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';

export default function DummyPage() {
  return (
    <div className="flex-1 w-full text-zinc-100 flex flex-col items-center justify-center font-sans mt-32">
      <h1 className="text-3xl font-bold mb-4">준비 중인 페이지입니다 🚀</h1>
      <p className="text-zinc-400 mb-8">MVP 개발 단계에서 아직 구현되지 않은 기능입니다.</p>
    </div>
  );
}
