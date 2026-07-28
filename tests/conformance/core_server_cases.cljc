;; Portable clojure.core.server/basilisp.core.server semantic coverage.
;;
;; Live socket-server objects, JVM Thread behavior, and Python socketserver
;; objects are host-shaped. This fixture covers shared public contracts that can
;; be checked without opening a long-lived socket: pREPL entrypoint surface,
;; REPL init/read hooks, stop absent/no-op behavior, start option rejection, and
;; property-driven start-servers no-op behavior.

#?(:clj (do
          (require '[clojure.core.server :as server])
          (import '[clojure.lang LineNumberingPushbackReader]
                  '[java.io StringReader]
                  '[java.util Properties]))
   :lpy (do
          (require '[clojure.core.server :as server])
          (import io)))

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(defn rejected? [f]
  (try
    (f)
    false
    (catch #?(:clj Throwable :lpy Exception) _ true)))

(defn reader-for [source]
  #?(:clj (LineNumberingPushbackReader. (StringReader. source))
     :lpy (io/StringIO source)))

(defn empty-server-properties []
  #?(:clj (Properties.)
     :lpy {}))

(emit-case :core-server-public-surface
           (every? #(contains? (ns-publics #?(:clj 'clojure.core.server
                                              :lpy 'basilisp.core.server))
                               %)
                   '[*session*
                     io-prepl
                     prepl
                     remote-prepl
                     repl
                     repl-init
                     repl-read
                     start-server
                     start-servers
                     stop-server
                     stop-servers]))

(emit-case :core-server-entrypoint-shapes
           {:session-dynamic? (:dynamic (meta #'server/*session*))
            :prepl-fn? (ifn? server/prepl)
            :io-prepl-fn? (ifn? server/io-prepl)
            :remote-prepl-fn? (ifn? server/remote-prepl)
            :repl-fn? (ifn? server/repl)
            :repl-init-fn? (ifn? server/repl-init)
            :repl-read-fn? (ifn? server/repl-read)
            :start-server-fn? (ifn? server/start-server)
            :start-servers-fn? (ifn? server/start-servers)
            :stop-server-fn? (ifn? server/stop-server)
            :stop-servers-fn? (ifn? server/stop-servers)})

(emit-case :session-binding-contract
           [server/*session*
            (binding [server/*session* {:name "fixture"}]
              (:name server/*session*))
            server/*session*])

(emit-case :repl-read-contract
           [(binding [*in* (reader-for "42")]
              (server/repl-read :prompt :exit))
            (binding [*in* (reader-for ":repl/quit")]
              (server/repl-read :prompt :exit))
            (binding [*in* (reader-for "")]
              (server/repl-read :prompt :exit))])

(emit-case :stop-contracts
           [(server/stop-server "definitely-missing-core-server")
            (server/stop-server)
            (server/stop-servers)])

(emit-case :start-validation-contracts
           {:invalid-port-rejected? (rejected?
                                     #(server/start-server
                                       {:port -1
                                        :name "bad-port"
                                        :accept 'clojure.core.server/repl}))
            :empty-start-servers (server/start-servers (empty-server-properties))})

(emit-case :repl-init-contract
           (let [before (ns-name *ns*)
                 result (server/repl-init)
                 after  (ns-name *ns*)]
             {:result result
              :changed-to-user? (= "user" (name after))
              :before-was-namespace? (some? before)}))
