open Core
    
module Target = struct
  
  type t = string
  [@@deriving sexp_of]
  
  module Name = struct
    type t = 
      | Executable of string
      | Library    of string
    [@@deriving sexp_of]
  end
  
  let targets_of_name name =
    let identifier = 
      match name with
      | Name.
          Executable x -> x
      | Library      x -> x
    in
    
    let id extn = 
      identifier ^ extn
    in
    let base =
      [ id ".cmi"
      ; id ".cmti"
      ; id ".cmx"
      ; id ".o"
      ; id ".a"
      ]
    in
    match name with 
    | Executable _ ->
      (id ".exe")::base
    | Library _ ->
      (id "")::base
end

type t = Target.t list
[@@deriving sexp_of]

let t_of_sexp sexp = 
  let get_target definition_type descriptor =
    let targets = List.filter_map descriptor ~f:(function
        | Sexp.List [ Sexp.Atom "name";  Sexp.Atom target]  -> Some [target]
        | Sexp.List [ Sexp.Atom "names"; Sexp.List targets] -> 
          let targets = List.map targets ~f:(function 
              | Sexp.Atom x -> Some x
              | _           -> None)
          in
          begin 
            match Option.all targets with
            | Some targets -> Some targets
            | None         -> None
          end
        | _ -> None)
    in
    let targets = 
      match targets with
      | [ targets ] -> targets
      | []          -> []
      | _           -> raise_s [%sexp "Found multiple targets in", (descriptor : Sexp.t list)]
    in
    match definition_type with
    | "executable" -> List.map targets ~f:(fun x -> Target.Name.Executable x |> Target.targets_of_name)
    | "library"    -> List.map targets ~f:(fun x -> Target.Name.Library    x |> Target.targets_of_name)
    | _            -> []
  in
  begin
    match sexp with  
    | Sexp.List
        [ Sexp.Atom definition_type
        ; Sexp.List descriptor] -> 
      get_target definition_type descriptor
    | _ -> []
  end
  |> List.concat