import React from "react";
import { ArrowRight, ShieldCheck, Sparkles } from "lucide-react";
import { motion } from "motion/react";

interface CallToActionProps {
  onStart: () => void;
}

export const CallToAction: React.FC<CallToActionProps> = ({ onStart }) => {
  return (
    <section className="py-20 sm:py-28 relative overflow-hidden bg-gradient-to-b from-[#f7fafc] to-[#e6f0ff]/50 border-t border-[#d8e3ef]/70">
      {/* Background visual accents */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[300px] bg-[#0b5fff]/8 blur-3xl -z-10 rounded-full" />

      <div className="max-w-4xl mx-auto px-4 sm:px-6 text-center">
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.4 }}
          className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider text-[#0b5fff] bg-[#e6f0ff] border border-[#0b5fff]/20 mb-6"
        >
          <Sparkles className="w-3.5 h-3.5" />
          <span>BẢN DEMO CHO SINH VIÊN</span>
        </motion.div>

        <motion.h2
          initial={{ opacity: 0, y: 14 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5, delay: 0.1 }}
          className="text-3xl sm:text-4xl md:text-5xl font-extrabold text-[#10253f] tracking-tight mb-5 leading-tight"
        >
          Hợp đồng là bước khởi đầu. <br />
          <span className="text-[#0b5fff]">Hiểu nó trước đã.</span>
        </motion.h2>

        <motion.p
          initial={{ opacity: 0, y: 14 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5, delay: 0.2 }}
          className="text-base sm:text-lg text-[#49627d] max-w-xl mx-auto mb-9 leading-relaxed"
        >
          Tạo không gian an toàn để bạn xem, hỏi và chuẩn bị trước mỗi cam kết
          quan trọng.
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 14 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5, delay: 0.3 }}
          className="flex flex-col sm:flex-row items-center justify-center gap-4"
        >
          <button
            onClick={onStart}
            className="w-full sm:w-auto inline-flex items-center justify-center gap-2.5 px-8 py-4 text-base font-semibold text-white bg-[#0b5fff] hover:bg-[#004ee6] rounded-xl shadow-xl shadow-[#0b5fff]/25 transition-all hover:scale-[1.02] active:scale-[0.98] cursor-pointer"
          >
            <span>Bắt đầu với hợp đồng của bạn</span>
            <ArrowRight className="w-5 h-5" />
          </button>
        </motion.div>
      </div>
    </section>
  );
};
