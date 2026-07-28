;; Portable clojure.core text, regex, and standard-input helpers. Outputs are
;; normalized to data values so platform line separators and host regex objects
;; do not affect differential comparison.

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(defn normalize-newlines [s]
  (when s
    (-> s
        (.replace "\r\n" "\n")
        (.replace "\r" "\n"))))

(defn rejected? [f]
  (try
    (f)
    false
    (catch #?(:clj Throwable :lpy python/Exception) _
      true)))

(emit-case :string-formatting-and-print-capture
           {:format [(format "plain")
                     (format "%s/%04d/%.2f" "x" 7 1.25)
                     (format "left=%-5s right=%5s" "a" "b")]
            :printf (let [ret (atom :unset)
                          out (with-out-str
                                (reset! ret (printf "value=%s/%d" "ok" 5)))]
                      [(normalize-newlines out) @ret])
            :newline (normalize-newlines (with-out-str (newline)))
            :print-str [(print-str)
                        (print-str "")
                        (print-str :kw "there" 3)
                        (print-str nil false "x")]
            :println-str [(normalize-newlines (println-str))
                          (normalize-newlines (println-str ""))
                          (normalize-newlines (println-str :kw "there" 3))]
            :prn-str [(normalize-newlines (prn-str))
                      (normalize-newlines (prn-str ""))
                      (normalize-newlines (prn-str :kw "there" 3))
                      (normalize-newlines (prn-str nil false "x"))]})

(emit-case :standard-input-reader-boundaries
           {:with-in-str [(with-in-str "alpha \n\nomega"
                           [(read-line)
                            (read-line)
                            (read-line)
                            (read-line)])
                         (with-in-str "crlf\r\nlast\r\n"
                           [(read-line)
                            (read-line)
                            (read-line)])
                         (with-in-str ""
                           [(read-line)])]
            :nested-input (with-in-str "outer\n"
                            [(read-line)
                             (with-in-str "inner\n"
                               [(read-line) (read-line)])
                             (read-line)])})

(emit-case :regex-pattern-matcher-and-seq
           (let [word-number (re-pattern "([a-z]+)(\\d*)")
                 matcher (re-matcher word-number "a1 b cc33")
                 first-found (.find matcher)
                 first-groups (re-groups matcher)
                 second-found (.find matcher)
                 second-groups (re-groups matcher)
                 third-found (.find matcher)
                 third-groups (re-groups matcher)
                 final-found (.find matcher)]
             {:pattern-use [(boolean (re-find (re-pattern "\\d+") "abc123"))
                            (re-find (re-pattern "\\d+") "abc")]
              :matcher [first-found
                        first-groups
                        second-found
                        second-groups
                        third-found
                        third-groups
                        final-found]
              :seq [(vec (re-seq (re-pattern "\\d+") "a1 bb22 c333"))
                    (vec (re-seq word-number "a1 b cc33"))
                    (seq (re-seq (re-pattern "[A-Z]+") "lowercase"))]
              :groups [(let [m (re-matcher (re-pattern "(a)?(b)") "b")]
                         [(.find m) (re-groups m)])
                       (rejected? #(re-groups (re-matcher #"x" "x")))]}))

(emit-case :seeded-text-regex-fuzz
           (mapv (fn [s]
                   {:input s
                    :digits (vec (re-seq (re-pattern "\\d+") s))
                    :words (vec (re-seq (re-pattern "[A-Za-z]+") s))
                    :printed [(print-str s)
                              (normalize-newlines (prn-str s))]
                    :formatted (format "[%s:%02d]" s (count s))})
                 ["a1 b22"
                  "plain"
                  "007 bond"
                  ""
                  "x9\ny10"]))
