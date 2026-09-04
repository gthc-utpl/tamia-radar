import useStore from '../../store/useStore'

const ICONS = {
  success: 'fa-check-circle text-green-400',
  error: 'fa-exclamation-circle text-red-400',
  warning: 'fa-exclamation-triangle text-yellow-400',
  info: 'fa-info-circle text-blue-400',
}

export default function ToastContainer() {
  const toasts = useStore((s) => s.toasts)
  const removeToast = useStore((s) => s.removeToast)

  if (toasts.length === 0) return null

  return (
    <div
      className="fixed top-16 left-1/2 -translate-x-1/2 z-[2000] flex flex-col gap-2 w-[90vw] max-w-sm"
      role="status"
      aria-live="polite"
    >
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className="flex items-center gap-3 bg-gray-900/95 backdrop-blur-md text-white
            text-sm px-4 py-3 rounded-xl shadow-xl border border-white/10
            animate-[slideDown_0.3s_ease-out]"
        >
          <i className={`fas ${ICONS[toast.type] || ICONS.info}`} />
          <span className="flex-1">{toast.message}</span>
          <button
            onClick={() => removeToast(toast.id)}
            className="w-6 h-6 flex items-center justify-center text-gray-400
              hover:text-white transition-colors shrink-0"
            aria-label="Cerrar notificación"
          >
            <i className="fas fa-times text-xs" />
          </button>
        </div>
      ))}
    </div>
  )
}
