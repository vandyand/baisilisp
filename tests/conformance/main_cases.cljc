;; Portable clojure.main/basilisp.main-compat conformance cases.

#?(:clj (require '[clojure.main :as main]
                 '[clojure.string :as str])
   :lpy (require '[clojure.main :as main]
                 '[clojure.string :as str]
                 '[clojure.tools.reader.reader-types :as reader-types]))

#?(:clj (import '[java.io StringReader]
                '[clojure.lang LineNumberingPushbackReader]))

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(defn reader [s]
  #?(:clj (LineNumberingPushbackReader. (StringReader. s))
     :lpy (reader-types/string-push-back-reader s)))

(defn next-char [r]
  #?(:clj (let [c (.read r)]
            (if (= -1 c) :eof (char c)))
     :lpy (or (reader-types/read-char r) :eof)))

(defn boom []
  (throw (#?(:clj RuntimeException.
             :lpy python/RuntimeError)
          "boom")))

(emit-case :public-surface
           (sort (map name (keys (ns-publics 'clojure.main)))))

(emit-case :reader-sentinels
           [(main/skip-if-eol (reader "\nabc"))
            (main/skip-if-eol (reader "abc"))
            (main/skip-if-eol (reader ""))
            (main/skip-whitespace (reader "  ,;comment\nabc"))
            (main/skip-whitespace (reader "abc"))
            (main/skip-whitespace (reader ""))])

(emit-case :crlf-reader-boundaries
           (vec
            (for [[op source] [[:skip-if-eol "\rabc"]
                               [:skip-if-eol "\r\nabc"]
                               [:skip-whitespace "\rabc"]
                               [:skip-whitespace "\r\nabc"]
                               [:skip-whitespace "  \rabc"]
                               [:skip-whitespace "  \r\nabc"]
                               [:skip-whitespace ";comment\rabc"]
                               [:skip-whitespace ";comment\r\nabc"]]]
              (let [r (reader source)
                    result (case op
                             :skip-if-eol (main/skip-if-eol r)
                             :skip-whitespace (main/skip-whitespace r))]
                [op result (next-char r)]))))

(emit-case :repl-read
           (let [r (reader "\n42\n99")]
             (binding [*in* r]
               [(main/repl-read :prompt :exit)
                (main/repl-read :prompt :exit)
                (main/repl-read :prompt :exit)
                (main/repl-read :prompt :exit)])))

(emit-case :remaining-helper-entrypoints
           {:demunge (main/demunge "foo_QMARK__BANG_")
            :renumbering-read (main/renumbering-read {:eof :eof} (reader "42") 99)
            :repl-exception (try
                              (boom)
                              (catch #?(:clj Throwable :lpy python/Exception) e
                                (ex-message (main/repl-exception e))))
            :root-cause (try
                          (boom)
                          (catch #?(:clj Throwable :lpy python/Exception) e
                            (ex-message (main/root-cause e))))
            :repl-prompt-suffix (str/ends-with? (with-out-str (main/repl-prompt))
                                                "=> ")
            :repl-requires (mapv first main/repl-requires)
            :err->msg? (try
                         (boom)
                         (catch #?(:clj Throwable :lpy python/Exception) e
                           (boolean (seq (main/err->msg e)))))
            :ex-triage-phase (:clojure.error/phase
                              (main/ex-triage {:clojure.error/phase :execution
                                               :clojure.error/cause "x"}))
            :host-bound-functions [(ifn? main/load-script)
                                   (ifn? main/main)
                                   (ifn? main/repl-caught)
                                   (ifn? main/report-error)
                                   (ifn? main/stack-element-str)]})

(emit-case :ex-str-portable
           [(main/ex-str {:clojure.error/phase :read-source
                          :clojure.error/source "sample.clj"
                          :clojure.error/line 4
                          :clojure.error/column 9
                          :clojure.error/cause "bad read"})
            (main/ex-str {:clojure.error/phase :macroexpansion
                          :clojure.error/source "sample.clj"
                          :clojure.error/line 2
                          :clojure.error/column 5
                          :clojure.error/symbol 'demo/m
                          :clojure.error/class 'java.lang.RuntimeException
                          :clojure.error/cause "bad macroexpand"})
            (main/ex-str {:clojure.error/phase :execution
                          :clojure.error/source "sample.clj"
                          :clojure.error/line 8
                          :clojure.error/column 1
                          :clojure.error/symbol 'demo/run
                          :clojure.error/class 'java.lang.RuntimeException
                          :clojure.error/cause "bad exec"})])

(emit-case :with-read-known
           (binding [*read-eval* :unknown]
             [(main/with-read-known *read-eval*)
              *read-eval*]))

(emit-case :with-bindings-dynamic-vars
           (binding [*print-namespace-maps* false
                     *1 :one
                     *2 :two
                     *3 :three
                     *e :error]
             [(main/with-bindings [*print-namespace-maps* *1 *2 *3 *e])
              [*print-namespace-maps* *1 *2 *3 *e]]))

(defn run-hooked-repl [forms]
  (let [state (atom forms)
        prompts (atom [])
        printed (atom [])
        flushes (atom 0)]
    (main/repl :need-prompt (fn [] true)
               :prompt #(swap! prompts conj :prompt)
               :flush #(swap! flushes inc)
               :read (fn [request-prompt request-exit]
                       (let [x (first @state)]
                         (swap! state rest)
                         (case x
                           :prompt request-prompt
                           :exit request-exit
                           x)))
               :eval (fn [x]
                       (if (= :boom x)
                         (throw (#?(:clj RuntimeException.
                                    :lpy python/RuntimeError)
                                  "boom"))
                         (inc x)))
               :print #(swap! printed conj %)
               :caught #(swap! printed conj [:caught (ex-message %)]))
    [@prompts @printed @flushes]))

(emit-case :option-driven-repl
           [(run-hooked-repl [1 2 :exit])
            (run-hooked-repl [:prompt 3 :exit])
            (run-hooked-repl [:boom :exit])])
