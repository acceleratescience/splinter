# ADR-002. Naming conventions for the server

Date: 2025-12-05
Status: Accepted
Status change:

## Context
A cool server needs a cool name. We have 4 powerful GPUs and our naming convention should match that power.

We considered many possibilities, including:

### Splinter
The server name shall be `splinter`, with each of the GPUs named after each of the Teenage Mutant Ninja Turtles:
- `leonardo` (disciplined and skilled)
- `raphael` (strong and quick tempered)
- `donatello` (smart and nerdy)
- `michelangelo` (fun-loving)

Given that our first endpoint will be split across GPUs 0 and 1, it is fitting that the two strongest and most aggressive turtles should take the honors. Also, people making spelling mistakes with the names will be funny.

Alternative shorter namings:

- `Leon` or Leo
- `Dona` or Donna
- `Rafa`
- `Mike`

### Hogwarts
The server name shall be `hogwarts` with each of the GPUs named after each of the houses at Hogwarts:
- `gryffindor` (Honour, valour, loyalty)
- `hufflepuff` (Honour and justice)
- `slytherin` (Where ambition meets cunning)
- `ravenclaw` (Engage, discuss, discover)

### The Jerk
Given that acceleration is the second order derivative of position with respect to time, it makes sense that we use the _third_ order derivative, which is jerk, and the higher order derivatives for the GPU names.

The server name shall therefore be `jerk`, with each of the GPUs named after each of the higher orders:
- `snap`
- `crackle`
- `pop`
- `lock`

## Decision
The server name shall be `splinter`, with each of the GPUs named after each of the Teenage Mutant Ninja Turtles. We have adapted the names to be shorter, and to be more gender inclusive:
- `leo` (disciplined and skilled)
- `raph` (strong and quick tempered)
- `dona` (smart and nerdy)
- `mike` (fun-loving)

## Consequences
There are no real consequences.
