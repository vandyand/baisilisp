;; Portable clojure.java.process/basilisp.java.process cases. Commands are
;; host-conditional, but each case compares the public Clojure-shaped process
;; contract: captured stdout, environment replacement, exit refs, and io-task
;; dynamic binding.

#?(:clj (require '[clojure.java.process :as p]
                 '[clojure.string :as str])
   :lpy (require '[clojure.java.process :as p]
                 '[basilisp.string :as str]))

#?(:lpy (import sys))

(def ^:dynamic *io-task-context* nil)

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(defn public-process-names []
  (sort (map name (keys (ns-publics #?(:clj 'clojure.java.process
                                        :lpy 'basilisp.java.process))))))

(defn command [& args]
  #?(:clj (into ["sh" "-c"] args)
     :lpy (into [sys/executable "-c"] args)))

(defn exec-command [program]
  (apply p/exec (command program)))

(defn normalize-newlines [s]
  (str/replace s "\r\n" "\n"))

(defn start-command
  ([program]
   (apply p/start (command program)))
  ([opts program]
   (apply p/start opts (command program))))

(emit-case :public-surface
           (public-process-names))

(emit-case :exec-stdout
           {:empty (exec-command #?(:clj "true"
                                    :lpy "pass"))
            :text (exec-command #?(:clj "printf '%s' 'hello process'"
                                   :lpy "print('hello process', end='')"))
            :multiline (normalize-newlines
                        (exec-command #?(:clj "printf 'a\nb\n'"
                                         :lpy "print('a'); print('b')")))
            :stderr-default (exec-command #?(:clj "printf '%s' 'stdout'; printf '%s' 'stderr' >&2"
                                             :lpy "import sys; print('stdout', end=''); print('stderr', file=sys.stderr, end='')"))})

(emit-case :environment-clear-and-merge
           {:clear (apply p/exec
                          {:clear-env true
                           :env {"BASILISP_PROCESS_CASE" "clear-value"}}
                          (command #?(:clj "printf '%s' \"$BASILISP_PROCESS_CASE\""
                                      :lpy "import os; print(os.environ['BASILISP_PROCESS_CASE'], end='')")))
            :merge (apply p/exec
                          {:env {"BASILISP_PROCESS_CASE" "merge-value"}}
                          (command #?(:clj "printf '%s' \"$BASILISP_PROCESS_CASE\""
                                      :lpy "import os; print(os.environ['BASILISP_PROCESS_CASE'], end='')")))})

(emit-case :exit-ref
           {:zero @(p/exit-ref (start-command #?(:clj "exit 0"
                                                 :lpy "import sys; sys.exit(0)")))
            :nonzero @(p/exit-ref (start-command #?(:clj "exit 7"
                                                    :lpy "import sys; sys.exit(7)")))
            :timeout (deref (p/exit-ref
                             (start-command #?(:clj "sleep 0.25"
                                               :lpy "import time; time.sleep(0.25)")))
                            1
                            :timed-out)})

(emit-case :io-task
           (let [task (binding [*io-task-context* :captured]
                        (p/io-task #(vector *io-task-context* "done")))]
             @task))

(emit-case :seeded-exec-corpus
           (loop [remaining 24
                  seed 271828
                  result []]
             (if (zero? remaining)
               result
               (let [next-seed (mod (+ (* seed 1103515245) 12345) 2147483648)
                     value (str "p" (mod next-seed 1000000))
                     source #?(:clj (str "printf '%s' '" value "'")
                               :lpy (str "print('" value "', end='')"))]
                 (recur (dec remaining)
                        next-seed
                        (conj result (exec-command source)))))))
