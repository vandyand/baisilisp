;; ``proxy-name`` has an intentionally host-native class label. Compare only
;; its useful stability and type properties; super dispatch is portable.

(ns conformance.proxy-helpers-cases)

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(def proxy-method #?(:clj "size"
                      :lpy "__len__"))

(defn proxy-count [value]
  #?(:clj (.size value)
     :lpy (python/len value)))

(let [proxy       #?(:clj (proxy [java.util.ArrayList] [] (size [] 99))
                     :lpy (proxy [python/list] [] (__len__ [] 99)))
      proxy-label (proxy-name #?(:clj java.util.ArrayList :lpy python/list) [])
      errors?     (try
                    (proxy-call-with-super (fn [] (throw (ex-info "broken" {})))
                                           proxy
                                           proxy-method)
                    false
                    (catch Exception _ true))]
  (emit-case :proxy-helpers
             {:name-string? (string? proxy-label)
              :name-stable? (= proxy-label
                               (proxy-name #?(:clj java.util.ArrayList :lpy python/list) []))
              :call-super? (= 0
                              (proxy-call-with-super #(proxy-count proxy) proxy proxy-method))
              :mapping-restored? (= 99 (proxy-count proxy))
              :exception-restored? (and errors? (= 99 (proxy-count proxy)))}))
