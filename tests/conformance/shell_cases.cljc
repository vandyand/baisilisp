;; Portable clojure.java.shell/basilisp.java.shell cases. Commands are
;; host-conditional, but each case compares the Clojure-shaped shell contract:
;; public surface, stdout/stderr/exit maps, stdin, environment and directory
;; bindings, byte output, and repeated command execution.

#?(:clj (require '[clojure.java.shell :as sh]
                 '[clojure.string :as str])
   :lpy (require '[clojure.java.shell :as sh]
                 '[basilisp.string :as str]))

#?(:lpy (import sys))

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(defn public-shell-names []
  (sort (map name (keys (ns-publics #?(:clj 'clojure.java.shell
                                        :lpy 'basilisp.java.shell))))))

(defn command [& args]
  #?(:clj (into ["sh" "-c"] args)
     :lpy (into [sys/executable "-c"] args)))

(defn normalize-result [result]
  (-> result
      (update :out #(str/replace % "\r\n" "\n"))
      (update :err #(str/replace % "\r\n" "\n"))))

(defn shell-command
  ([program]
   (normalize-result (apply sh/sh (command program))))
  ([program & opts]
   (normalize-result (apply sh/sh (concat (command program) opts)))))

(defn out-command [program & opts]
  (:out (apply shell-command program opts)))

(emit-case :public-surface
           (public-shell-names))

(emit-case :basic-result-map
           (normalize-result
            (apply sh/sh
                   (command #?(:clj "printf '%s' 'stdout'; printf '%s' 'stderr' >&2; exit 7"
                               :lpy "import sys; print('stdout', end=''); print('stderr', file=sys.stderr, end=''); sys.exit(7)")))))

(emit-case :stdin-and-encoding
           {:text (:out (apply shell-command
                               #?(:clj ["cat" :in "hello\nthere"]
                                  :lpy ["import sys; print(sys.stdin.read(), end='')" :in "hello\nthere"])))
            :bytes (vec (:out (apply sh/sh
                                     (concat (command #?(:clj "printf '%s' 'ABC'"
                                                         :lpy "import sys; sys.stdout.write('ABC')"))
                                             [:out-enc :bytes]))))})

(emit-case :environment
           {:explicit (out-command #?(:clj "printf '%s' \"$BASILISP_SHELL_CASE\""
                                      :lpy "import os; print(os.environ['BASILISP_SHELL_CASE'], end='')")
                                   :env {"BASILISP_SHELL_CASE" "explicit"})
            :bound (sh/with-sh-env {"BASILISP_SHELL_CASE" "bound"}
                     (out-command #?(:clj "printf '%s' \"$BASILISP_SHELL_CASE\""
                                     :lpy "import os; print(os.environ['BASILISP_SHELL_CASE'], end='')")))
            :explicit-over-bound (sh/with-sh-env {"BASILISP_SHELL_CASE" "bound"}
                                   (out-command #?(:clj "printf '%s' \"$BASILISP_SHELL_CASE\""
                                                   :lpy "import os; print(os.environ['BASILISP_SHELL_CASE'], end='')")
                                                :env {"BASILISP_SHELL_CASE" "explicit"}))})

(emit-case :directory-binding
           (sh/with-sh-dir "tests"
             (str/trim
              (out-command #?(:clj "basename \"$PWD\""
                              :lpy "import pathlib; print(pathlib.Path.cwd().name)")))))

(defn next-seed [seed]
  (mod (+ (* seed 1103515245) 12345) 2147483648))

(emit-case :seeded-command-corpus
           (loop [remaining 24
                  seed 424242
                  result []]
             (if (zero? remaining)
               result
               (let [next (next-seed seed)
                     value (str "s" (mod next 1000000))
                     program #?(:clj (str "printf '%s' '" value "'")
                                :lpy (str "print('" value "', end='')"))]
                 (recur (dec remaining)
                        next
                        (conj result (:out (shell-command program))))))))
