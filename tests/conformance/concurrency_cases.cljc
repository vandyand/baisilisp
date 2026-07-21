;; Deterministic portable Agent and Ref cases. These avoid scheduler-sensitive
;; timing claims while proving public coordination behavior in both runtimes.

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(let [agent-state (agent 0)
      _send (send agent-state + 2)
      waited (await-for 1000 agent-state)
      value @agent-state]
  (emit-case :agent-send {:waited waited :value value}))

(let [agent-state (agent 0)
      ref-state (ref 0)
      result (dosync
              (alter ref-state inc)
              (send agent-state + 2)
              :committed)
      waited (await-for 1000 agent-state)
      values [@ref-state @agent-state]]
  (emit-case :transactional-agent-send
             {:result result :waited waited :values values}))

(let [agent-state (agent 0)
      _send (send agent-state + 3)
      waited #?(:clj (await agent-state)
                :lpy (clojure.core/await agent-state))]
  (emit-case :agent-await
             {:waited waited :value @agent-state
              :await-for (await-for 1000 agent-state)
              :released (release-pending-sends)}))

(let [agent-state (agent 0)
      _send (send agent-state + 4)
      returned (await1 agent-state)]
  (emit-case :agent-await1
             {:same-agent (identical? returned agent-state)
              :value @agent-state}))

(let [value (atom 0)
      events (atom [])]
  (add-watch value :record (fn [_ _ old new] (swap! events conj [old new])))
  (swap! value + 3)
  (emit-case :atom-watch {:value @value :events @events}))

(let [value (ref 1)
      result (sync nil (alter value + 4) :synced)]
  (emit-case :sync {:result result :value @value}))

;; Clojure's global Agent executors keep a command-line process alive. This is
;; process cleanup after all observable cases, not part of the parity contract.
#?(:clj (shutdown-agents)
   :lpy nil)
