;; Portable clojure.java.process/basilisp.java.process cases. Commands are
;; host-conditional, but each case compares the public Clojure-shaped process
;; contract: captured stdout, environment replacement, exit refs, and io-task
;; dynamic binding.

#?(:clj (require '[clojure.java.process :as p]
                 '[clojure.string :as str])
   :lpy (require '[clojure.java.process :as p]
                 '[basilisp.string :as str]))

#?(:clj (import '[java.io File]
                '[java.nio.file Files])
   :lpy (import sys tempfile pathlib os))

(def ^:dynamic *io-task-context* nil)

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(defn rejected? [f]
  (try
    (f)
    false
    (catch #?(:clj Throwable :lpy python/Exception) _
      true)))

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

(defn temp-path []
  #?(:clj (let [f (File/createTempFile "basilisp-process" ".txt")]
            (.deleteOnExit f)
            (.getAbsolutePath f))
     :lpy (let [f (tempfile/NamedTemporaryFile ** :delete false)]
            (let [path (.-name f)]
              (.close f)
              path))))

(defn delete-path [path]
  #?(:clj (.delete (File. path))
     :lpy (os/remove path)))

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

(emit-case :stream-accessors
           (let [proc (start-command
                       {:encoding "utf-8"}
                       #?(:clj "printf '%s' 'stream-out'; printf '%s' 'stream-err' >&2"
                          :lpy "import sys; print('stream-out', end=''); print('stream-err', file=sys.stderr, end='')"))
                 stdin? (some? (p/stdin proc))
                 out (slurp (p/stdout proc))
                 err (slurp (p/stderr proc))
                 exit @(p/exit-ref proc)]
             {:stdin? stdin?
              :stdout out
              :stderr err
              :exit exit}))

(emit-case :file-redirects
           (let [in-path (temp-path)
                 out-path (temp-path)]
             (try
               (spit in-path "file-input")
               (let [proc (apply p/start
                                 {:in (p/from-file in-path)
                                  :out (p/to-file out-path)
                                  :encoding "utf-8"}
                                 (command #?(:clj "cat"
                                             :lpy "import sys; print(sys.stdin.read(), end='')")))
                     exit @(p/exit-ref proc)]
                 {:exit exit
                  :output (slurp out-path)
                  :from-file? (some? (p/from-file in-path))
                  :to-file? (some? (p/to-file out-path))})
               (finally
                 (delete-path in-path)
                 (delete-path out-path)))))

(emit-case :adversarial-stdio-and-redirects
           (let [append-path (temp-path)]
             (try
               (spit append-path "before\n")
               (let [stdin-proc (start-command
                                  {:encoding "utf-8"}
                                  #?(:clj "cat"
                                     :lpy "import sys; print(sys.stdin.read(), end='')"))
                     stdin-stream (p/stdin stdin-proc)
                     _ #?(:clj (.write stdin-stream (.getBytes "pipe-input" "UTF-8"))
                          :lpy (.write stdin-stream "pipe-input"))
                     _ (.close stdin-stream)
                     stdin-out (slurp (p/stdout stdin-proc))
                     stdin-exit @(p/exit-ref stdin-proc)
                     merged-proc (start-command
                                  {:encoding "utf-8" :err :stdout}
                                  #?(:clj "printf '%s' 'out'; printf '%s' '+err' >&2"
                                     :lpy "import sys; print('out', end=''); print('+err', file=sys.stderr, end='')"))
                     discarded-proc (start-command
                                     {:encoding "utf-8" :out :discard :err :discard}
                                     #?(:clj "printf '%s' 'out'; printf '%s' 'err' >&2"
                                        :lpy "import sys; print('out', end=''); print('err', file=sys.stderr, end='')"))
                     append-a (apply p/start
                                     {:out (p/to-file append-path :append true)
                                      :encoding "utf-8"}
                                     (command #?(:clj "printf 'middle\n'"
                                                 :lpy "print('middle')")))]
                 @(p/exit-ref append-a)
                 (let [append-b (apply p/start
                                       {:out (p/to-file append-path :append true)
                                        :encoding "utf-8"}
                                       (command #?(:clj "printf 'after\n'"
                                                   :lpy "print('after')")))]
                   @(p/exit-ref append-b))
                 {:stdin {:out stdin-out :exit stdin-exit}
                  :merged {:out (slurp (p/stdout merged-proc))
                           :err-stream? (nil? (p/stderr merged-proc))
                           :exit @(p/exit-ref merged-proc)}
                  :discarded {:stdout? (nil? (p/stdout discarded-proc))
                              :stderr? (nil? (p/stderr discarded-proc))
                              :exit @(p/exit-ref discarded-proc)}
                  :append (slurp append-path)})
               (finally
                 (delete-path append-path)))))

(emit-case :adversarial-dir-and-error-contracts
           (let [root #?(:clj (str (Files/createTempDirectory
                                    "basilisp-process-dir"
                                    (make-array java.nio.file.attribute.FileAttribute 0)))
                         :lpy (tempfile/mkdtemp ** :prefix "basilisp-process-dir"))
                 child #?(:clj (str (File. root "child"))
                          :lpy (str (pathlib/Path root "child")))]
             #?(:clj (.mkdirs (File. child))
                :lpy (.mkdir (pathlib/Path child) ** :parents true :exist_ok true))
             {:dir (str/trim
                    (apply p/exec
                           {:dir child}
                           (command #?(:clj "basename \"$PWD\""
                                       :lpy "import pathlib; print(pathlib.Path.cwd().name)"))))
              :nonzero-rejected? (rejected?
                                  #(apply p/exec
                                          (command #?(:clj "exit 11"
                                                      :lpy "import sys; sys.exit(11)"))))
              :clear-env-missing (apply p/exec
                                        {:clear-env true}
                                        (command #?(:clj "printf '%s' \"$BASILISP_PROCESS_ABSENT\""
                                                    :lpy "import os; print(os.environ.get('BASILISP_PROCESS_ABSENT', ''), end='')")))
              :explicit-encoding (apply p/exec
                                        {:encoding "utf-8"}
                                        (command #?(:clj "printf '%s' 'process-ok'"
                                                    :lpy "print('process-ok', end='')")))}))

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
