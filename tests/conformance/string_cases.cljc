;; Portable clojure.string/basilisp.string public surface and newline trimming
;; cases. This fixture focuses on the Clojure-compatible namespace contract;
;; Basilisp's extra Python-native string helpers are covered by local tests.

(require '[clojure.string :as str])

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(emit-case :public-surface
           {:has-trim-newline?
            (contains? (ns-publics #?(:clj 'clojure.string
                                      :lpy 'basilisp.string))
                       'trim-newline)})

(emit-case :trim-newline
           (mapv str/trim-newline
                 [""
                  "\n"
                  "\r"
                  "\r\n"
                  "alpha\n"
                  "alpha\r\n"
                  "alpha\n\n"
                  "alpha\r\r"
                  "alpha\n\r"
                  "alpha\t "
                  "alpha \n beta"]))
