(ns conformance.print-writer-cases)

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(let [flushed (atom [])
      closed  (atom 0)
      writer  (PrintWriter-on #(swap! flushed conj %) #(swap! closed inc))]
  (.write writer "first")
  (.flush writer)
  (.write writer 65)
  (.write writer "second")
  (.close writer)
  (emit-case :flush-close
             {:flushed @flushed
              :closed @closed}))
