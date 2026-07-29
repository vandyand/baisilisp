;   Copyright (c) Rich Hickey. All rights reserved.
;   The use and distribution terms for this software are covered by the
;   Eclipse Public License 1.0 (http://opensource.org/licenses/eclipse-1.0.php)
;   which can be found in the file epl-v10.html at the root of this distribution.
;   By using this software in any fashion, you are agreeing to be bound by
;   the terms of this license.
;   You must not remove this notice, or any other, from this software.

(ns ^{:doc "A unification library for Clojure."
      :author "Michael Fogus"}
  basilisp.core.unify
  (:require #?(:lpy [basilisp.zip :as zip]
               :default [clojure.zip :as zip])
            #?(:lpy [basilisp.walk :as walk]
               :default [clojure.walk :as walk])))

(defn ignore-variable? [sym] (= '_ sym))

;; ### Utilities

(def ^{:doc "Returns true if a symbol represents a core.unify lvar.
 By default, core.unify expects a symbol starting with ? or just _."}
  lvar? #(or (ignore-variable? %)
             (and (symbol? %) (re-matches #"^\?.*" (name %)))))

(defn extract-lvars
  "Takes a datastructure form and returns a distinct set of the logical
  variables found within. By default, the lvar? predicate is used to detect nested
  lvars, but the function also accepts a custom predciate lv-fn to use instead."
  ([form]
     (extract-lvars lvar? form))
  ([lv-fn form]
     (set
      (walk/walk #(when (lv-fn %) %)
                 #(keep identity %)
                 form))))

(defn- ^:no-doc composite?
  "Taken from the old `contrib.core/seqable?`. Since the meaning of 'seqable' is
   questionable, I will work on phasing it out and using a more meaningful
   predicate.  At the moment, the only meaning of `composite?` is:
   Returns true if `(seq x)` will succeed, false otherwise."
  [x]
  #?(:clj (or (coll? x)
              (nil? x)
              (instance? Iterable x)
              (-> x class .isArray)
              (string? x)
              (instance? java.util.Map x))
     :lpy (seqable? x)
     :cljs (seqable? x)))

(declare garner-unifiers)

(defn- ^:no-doc occurs?
  "Does v occur anywhere inside expr?"
  [variable? v expr binds]
  (loop [z (zip/zipper composite? seq #(do % %2) [expr])]
    (let [current (zip/node z)]
      (cond
        (zip/end? z) false
        (= v current) true
        (and (variable? current)
             (find binds current))
        (recur (zip/next (zip/insert-right z (binds current))))
        :else (recur (zip/next z))))))

(defn- ^:no-doc bind-phase
  [binds variable expr]
  (if (or (nil? expr)
          (ignore-variable? variable))
    binds
    (assoc binds variable expr)))

(defn- ^:no-doc determine-occursness
  [want-occurs? variable? v expr binds]
  (if want-occurs?
    `(if (occurs? ~variable? ~v ~expr ~binds)
       #?(:clj  (throw (IllegalStateException. (str "Cycle found in the path " ~expr)))
          :lpy  (throw (python/RuntimeError (str "Cycle found in the path " ~expr)))
          :cljs (throw (js/Error. (str "Cycle found in the path " ~expr))))
       (bind-phase ~binds ~v ~expr))
    `(bind-phase ~binds ~v ~expr)))

#?(:clj
   (defmacro ^:no-doc create-var-unification-fn
     [want-occurs?]
     (let [varp  (gensym)
           v     (gensym)
           expr  (gensym)
           binds (gensym)
           self  (gensym)]
       `(fn ~self
          [~varp ~v ~expr ~binds]
          (if-let [vb# (~binds ~v)]
            (garner-unifiers ~self ~varp vb# ~expr ~binds)
            (if-let [vexpr# (and (~varp ~expr) (~binds ~expr))]
              (garner-unifiers ~self ~varp ~v vexpr# ~binds)
              ~(determine-occursness want-occurs? varp v expr binds))))))
   :lpy
   (defmacro ^:no-doc create-var-unification-fn
     [want-occurs?]
     (let [varp  (gensym)
           v     (gensym)
           expr  (gensym)
           binds (gensym)
           self  (gensym)]
       `(fn ~self
          [~varp ~v ~expr ~binds]
          (if-let [vb# (~binds ~v)]
            (garner-unifiers ~self ~varp vb# ~expr ~binds)
            (if-let [vexpr# (and (~varp ~expr) (~binds ~expr))]
              (garner-unifiers ~self ~varp ~v vexpr# ~binds)
              ~(determine-occursness want-occurs? varp v expr binds)))))))

(def ^{:doc "Unify the variable v with expr.  Uses the bindings supplied and possibly returns an extended bindings map."
       :no-doc true
       :private true}
  unify-variable (create-var-unification-fn true))

(def ^{:doc "Unify the variable v with expr.  Uses the bindings supplied and possibly returns an extended bindings map."
       :no-doc true
       :private true}
  unify-variable- (create-var-unification-fn false))

(defn wildcard?
  "Returns true if form starts with a core.unify wildcard. By default, core.unify expects the symbol &."
  [form]
  (and (composite? form)
       (#{'&} (first form))))

(defn- ^:no-doc garner-unifiers
  ([x y]                 (garner-unifiers unify-variable lvar? x y {}))
  ([variable? x y]       (garner-unifiers unify-variable variable? x y {}))
  ([variable? x y binds] (garner-unifiers unify-variable variable? x y binds))
  ([uv-fn variable? x y binds]
     (cond
      (not binds)               nil
      (= x y)                   binds
      (variable? x)             (uv-fn variable? x y binds)
      (variable? y)             (uv-fn variable? y x binds)
      (wildcard? x)             (uv-fn variable? (second x) (seq y) binds)
      (wildcard? y)             (uv-fn variable? (second y) (seq x) binds)
      (every? composite? [x y]) (garner-unifiers uv-fn
                                                 variable?
                                                 (rest x)
                                                 (rest y)
                                                 (garner-unifiers uv-fn
                                                                  variable?
                                                                  (first x)
                                                                  (first y)
                                                                  binds)))))

(defn flatten-bindings
  "Flattens recursive bindings in binds to the same ground, if possible.
  If a variable cannot be resolved then it is left in place."
  ([binds] (flatten-bindings lvar? binds))
  ([variable? binds]
   (into {}
         (map (fn [[k v]]
                [k (loop [v v]
                     (if-let [entry (and (variable? v) (find binds v))]
                       (recur (val entry))
                       v))])
              binds))))

(defn- ^:no-doc try-subst
  [variable? x binds]
  {:pre [(map? binds) (fn? variable?)]}
  (walk/prewalk (fn [expr]
                  (if (variable? expr)
                    (if-let [bind (find binds expr)]
                      (val bind)
                      expr)
                    expr))
                x))

(defn- ^:no-doc unifier*
  ([x y] (unifier* lvar? x y))
  ([variable? x y]
     (unifier* variable? x y (garner-unifiers variable? x y)))
  ([variable? x y binds]
     (->> binds
          (flatten-bindings variable?)
          (try-subst variable? y))))

;; ## OCCURS

(defn make-occurs-unify-fn
  "Given a function to recognize logic variables, returns a function to
   return a bindings map for two expressions.  This function uses an 'occurs check'
   to detect cycles."
  [variable-fn]
  (fn
    ([x y] (garner-unifiers unify-variable variable-fn x y {}))
    ([x y binds] (garner-unifiers unify-variable variable-fn x y binds))))

(defn make-occurs-subst-fn
  "Given a function to recognize logic variables, returns a function that
   will attempt to substitute unification bindings between two expressions.
   This function uses an 'occurs check'."
  [variable-fn]
  (partial try-subst variable-fn))

(defn make-occurs-unifier-fn
  "Given a function to recognize logic variables, returns a function to
   perform the unification of two expressions. This function uses an 'occurs check'
   to detect cycles."
  [variable-fn]
  (partial unifier* variable-fn))

(def ^{:doc "Attempts to unify x and y with the given bindings (if any). May return a map of the
unifiers (bindings) found. Will throw if an 'occurs check' determines that the expressions contain
cyclic bindings or if the sub-expressions clash."
       :arglists '([expression1 expression2])}
  unify   (make-occurs-unify-fn lvar?))

(def ^{:doc "Attempts to substitute the logic variables within an expression with their mapped values in bindings."
       :arglists '([expression bindings])}
  subst   (make-occurs-subst-fn lvar?))

(def ^{:doc "Attempts the entire unification process from garnering the bindings to substituting
     the appropriate bindings, using an 'occurs check'."
       :arglists '([expression1 expression2])}
  unifier (make-occurs-unifier-fn lvar?))

;; ## NO OCCURS

(defn make-unify-fn
  "Given a function to recognize unification variables, returns a function to
  return a bindings map for two expressions without an 'occurs check'."
  [variable-fn]
  (fn
    ([x y] (garner-unifiers unify-variable- variable-fn x y {}))
    ([x y binds] (garner-unifiers unify-variable- variable-fn x y binds))))

(defn make-subst-fn
  "Given a function to recognize unification variables, returns a function that
  will attempt to substitute unification bindings between two expressions
  without an 'occurs check'."
  [variable-fn]
  (partial try-subst variable-fn))

(defn make-unifier-fn
  "Given a function to recognize unification variables, returns a function to
  perform the unification of two expressions without an 'occurs check'."
  [variable-fn]
  (fn [x y]
    (unifier* variable-fn
              x
              y
              (garner-unifiers unify-variable- variable-fn x y {}))))

(def ^{:doc "Attempt to unify x and y with the given bindings (if any). May return a map of the
unifiers (bindings) found. Will throw if the sub-expressions clash. This function is not guranteed
to terminate if cyclic logic variables are present."
       :arglists '([expression1 expression2])}
  unify-   (make-unify-fn lvar?))

(def ^{:doc "Attempts the entire unification process from garnering the bindings to substituting
the appropriate bindings. This function is not guranteed to terminate if cyclic logic variables
are present."
       :arglists '([expression1 expression2])}
  unifier- (make-unifier-fn lvar?))
