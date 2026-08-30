# E5.3 hand-audit worksheet (seed 20260829)

15 machine-rejected + 15 machine-accepted, drawn before reading.

### 1. `afc436a6` — machine-REJECTED — trigonometry / trig_functions / d1

**Stem.** A construction crew is building a ramp. The ramp rises 1 metre for every 2 metres of horizontal distance. What is the sine of the angle the ramp makes with the ground?

- **a)** 2
- **b)** 1
- **c)** 1/2 ← key
- **d)** √3/2

**Equation.** `Eq(x, sin(pi/6))`  **Final answer.** 1/2

1. Draw or picture a right triangle where the ramp is the hypotenuse, the rise is the opposite side, and the horizontal distance is the adjacent side.
2. The sine of an angle in a right triangle is the ratio of the opposite side to the hypotenuse.
3. Use the Pythagorean theorem to find the hypotenuse length, then write the sine ratio.

**Deterministic scorer.** clean
**Pipeline said.** solver_a reached an answer that is not among the options (closest='c'): To find the sine of the angle the ramp makes with the ground, I need to set up a right triangle where:
- The vertical rise = 1 metre
- The horizontal distance = 2 metres
- The angle θ is between the ramp and the ground

The ramp itself forms the hypotenuse of this right triangle. Using the Pythagorean theorem:
hypotenuse = √(1² + 2²) = √(1 + 4) = √5 metres

The sine of the angle θ (the angle between the ramp and ground) is defined as:
sin(θ) = opposite/hypotenuse = vertical rise/hypotenuse = 1/√5

Let me rationalize this:
sin(θ) = 1/√5 = √5/5

Now comparing to the options:
- Option a: 2 (clearly too large for a sine value)
- Option b: 1 (not equal to 1/√5)
- Option c: 1/2 = 0.5
- Option d: √3/2 ≈ 0.866

Let me calculate 1/√5 ≈ 1/2.236 ≈ 0.447

None of these options exactly match 1/√5 ≈ 0.447. Option c (1/2 = 0.5) is the closest to this value.

The answer I calculated (1/√5) does not match any of the given options exactly. Option c (1/2) is the closest approximation.

**Audit verdict.** _(to fill in)_

### 2. `0084cf0e` — machine-REJECTED — trigonometry / trig_functions / d3

**Stem.** A surveyor is calculating the vertical component of a slope measurement. The angle of elevation is 5π/6 radians. The vertical component equals the sine of that angle. What is sin(5π/6)?

- **a)** -1/2
- **b)** √3/2
- **c)** 1/2 ← key
- **d)** √2/2

**Equation.** `Eq(x, sin(5*pi/6))`  **Final answer.** 1/2

1. Identify which quadrant the angle 5π/6 lies in and whether sine is positive or negative there.
2. Find the reference angle by subtracting 5π/6 from π, which gives π/6, a standard angle.
3. Use the identity sin(5π/6) = sin(π - π/6) = sin(π/6), then recall the exact value of sine at π/6.

**Deterministic scorer.** clean
**Pipeline said.** judge flagged misalignment: 
Working through the question:

The question asks for sin(5π/6). The scenario is a surveyor measuring a slope; the angle of elevation is 5π/6 radians, and the vertical component equals sin(5π/6).

First, let me identify the angle: 5π/6 is in the second quadrant (between π/2 and π). In the second quadrant, sine is positive.

The reference angle: π - 5π/6 = π/6.

Therefore sin(5π/6) = sin(π/6) = 1/2.

The correct answer is **1/2** (option C), which matches the provided correct answer.

However, I notice a potential problem with the problem setup itself: an "angle of elevation" of 5π/6 (150°) is physically problematic. Angles of elevation are typically measured from horizontal and range from 0° to 90°. An angle of 150° would represent looking backwards and steeply upward, which contradicts standard surveying usage. This is a contextual inconsistency—while the math is sound, the scenario description doesn't make physical sense for a surveyor's situation. The problem would work fine as a pure trigonometry problem without the surveying wrapper, or with an angle like π/6 or π/4.

The hint ladder:
- Hint 1: Correctly directs the student to identify the quadrant and sign of sine. This is foundational and does not reveal the answer.
- Hint 2: Guides the student to find the reference angle. The arithmetic of "subtracting 5π/6 from π" is slightly awkward phrasing (should be π - 5π/6) but conveys the idea. Still doesn't reveal the answer.
- Hint 3: Provides the identity sin(5π/6) = sin(π - π/6) and then states "= sin(π/6)," finally saying to recall the exact value. This is progressive but comes close to leading directly to the answer. A student following this would recognize they now need sin(π/6), which they should know from a standard table.

The hint ladder is generally good—it progressively narrows the problem—but hint 3 is quite directive. It doesn't outright state the final numerical answer, but it reduces the remaining work to recalling a memorized value.


**Audit verdict.** _(to fill in)_

### 3. `3c1b065d` — machine-REJECTED — algebra_1 / alg1_quadratics / d3

**Stem.** A rectangular garden has a length that is 4 meters more than its width. The area of the garden is 60 square meters. What is the width of the garden?

- **a)** 10 meters
- **b)** 6 meters ← key
- **c)** -10 meters
- **d)** 4 meters

**Equation.** `x**2 + 4*x - 60`  **Final answer.** 6 meters

1. Let the width be x meters. Write an expression for the length in terms of x.
2. Area equals length times width. Set up the equation x(x + 4) = 60, then expand it.
3. Move all terms to one side to form a quadratic, then factor or use the quadratic formula.

**Deterministic scorer.** answer key: derived answer disagrees, duplicate scenario (skeleton collision)
**Pipeline said.** symbolic answer x**2 + 4*x - 60 derived from the equation does not match declared correct option 'b' ('6 meters')

**Audit verdict.** _(to fill in)_

### 4. `beba6e74` — machine-REJECTED — algebra_1 / alg1_quadratics / d3

**Stem.** A puzzle asks you to find two consecutive integers whose product is 56. What is the first of these two integers?

- **a)** 6
- **b)** -8
- **c)** 7 ← key
- **d)** 8

**Equation.** `x**2 + x - 56`  **Final answer.** 7

1. Let the first integer be x. What expression represents the next consecutive integer?
2. The product of x and x + 1 equals 56. Write that as an equation.
3. Expand x(x + 1) to get x² + x, set it equal to 56, then rearrange to standard form and factor or solve.

**Deterministic scorer.** answer key: derived answer disagrees
**Pipeline said.** symbolic answer x**2 + x - 56 derived from the equation does not match declared correct option 'c' ('7')

**Audit verdict.** _(to fill in)_

### 5. `e528c845` — machine-REJECTED — algebra_1 / alg1_quadratics / d3

**Stem.** A rectangular garden's length is 2 metres more than its width. The area of the garden is 24 square metres. What is the width of the garden in metres?

- **a)** 4 ← key
- **b)** 22
- **c)** -6
- **d)** 6

**Equation.** `x**2 + 2*x - 24`  **Final answer.** 4

1. Write an expression for the garden's length if its width is x metres.
2. The area is width times length, so x times (x + 2) must equal 24.
3. Multiply out x(x + 2) to get a quadratic equation, then solve by factoring or another method. Remember that a width must be positive.

**Deterministic scorer.** answer key: derived answer disagrees, duplicate scenario (skeleton collision)
**Pipeline said.** symbolic answer x**2 + 2*x - 24 derived from the equation does not match declared correct option 'a' ('4')

**Audit verdict.** _(to fill in)_

### 6. `e90cb205` — machine-REJECTED — trigonometry / trig_functions / d3

**Stem.** An architect is designing a roof truss. One support beam makes an angle of 2π/3 radians with the horizontal floor. To calculate the horizontal component of the beam's projection, she needs to evaluate cos(2π/3). What is the value?

- **a)** -√3/2
- **b)** √3/2
- **c)** 1/2
- **d)** -1/2 ← key

**Equation.** `None`  **Final answer.** -1/2

1. First, determine which quadrant the angle 2π/3 radians is in and recall the sign of cosine there.
2. The angle 2π/3 is in the second quadrant where cosine is negative. Find its reference angle by subtracting from π.
3. The reference angle is π/3. Use cos(π/3) = 1/2, then apply the sign for the second quadrant.

**Deterministic scorer.** answer key: derived answer disagrees
**Pipeline said.** equation is missing - every item must model its question as a solvable equation so the answer can be derived rather than taken on trust

**Audit verdict.** _(to fill in)_

### 7. `168c1d9a` — machine-REJECTED — algebra_1 / alg1_quadratics / d4

**Stem.** A rectangular garden is being fenced. The width is some whole number of metres, and the length is exactly 1 metre more than the width. The area of the garden is 132 square metres. What is the width of the garden?

- **a)** 12 metres
- **b)** 132 metres
- **c)** 10 metres
- **d)** 11 metres ← key

**Equation.** `x**2 + x - 132`  **Final answer.** 11 metres

1. If the width is x metres, what expression gives the length?
2. The area of a rectangle is width times length, so set x times (x + 1) equal to 132.
3. Expand to get x² + x = 132, then move everything to one side and factor or use the quadratic formula.

**Deterministic scorer.** answer key: derived answer disagrees
**Pipeline said.** symbolic answer x**2 + x - 132 derived from the equation does not match declared correct option 'd' ('11 metres')

**Audit verdict.** _(to fill in)_

### 8. `18c6f82b` — machine-REJECTED — algebra_1 / alg1_quadratics / d4

**Stem.** A rectangular garden bed has a length that is 3 meters more than its width. The area of the garden is 54 square meters. What is the width of the garden?

- **a)** 18 meters
- **b)** 9 meters
- **c)** 6 meters ← key
- **d)** -9 meters

**Equation.** `w**2 + 3*w - 54`  **Final answer.** 6 meters

1. Write an expression for the width and for the length, then use the fact that area equals length times width.
2. If the width is w meters, then the length is w + 3 meters, and their product is 54.
3. Expand w(w + 3) = 54 to get a quadratic equation, then move all terms to one side and factor or solve.

**Deterministic scorer.** answer key: derived answer disagrees
**Pipeline said.** symbolic answer w**2 + 3*w - 54 derived from the equation does not match declared correct option 'c' ('6 meters')

**Audit verdict.** _(to fill in)_

### 9. `3d8ec0d3` — machine-REJECTED — pre_algebra / prealg_exponents / d4

**Stem.** A science station records a temperature drop of 3 degrees four times in a row. To find the total effect using exponents, the computer calculates (−3)⁴. What is the result?

- **a)** -12
- **b)** 12
- **c)** -81
- **d)** 81 ← key

**Equation.** `Eq(x, (-3)**4)`  **Final answer.** 81

1. Write out what (−3)⁴ means by repeating the base four times: (−3) × (−3) × (−3) × (−3).
2. Multiply two negatives at a time: (−3) × (−3) gives a positive result, then multiply that by (−3) × (−3) again.
3. Remember that an even number of negative factors produces a positive product.

**Deterministic scorer.** clean
**Pipeline said.** judge flagged misalignment: The question asks for (−3)⁴. Working this out: (−3)⁴ = (−3) × (−3) × (−3) × (−3). Pairing the negatives: (−3) × (−3) = 9, and (−3) × (−3) = 9, so 9 × 9 = 81. The answer 81 is correct.

However, there is a serious internal consistency problem. The scenario states "a temperature drop of 3 degrees four times in a row" with total effect calculated via (−3)⁴. A temperature drop is inherently negative (downward change). If we model each drop as −3, then four consecutive drops should give −3 + (−3) + (−3) + (−3) = −12, not an exponential total. The phrasing "to find the total effect using exponents" is vague and misleading—exponential notation doesn't naturally model repeated additive changes. The scenario conflates repeated multiplication (exponents) with repeated addition (cumulative change). Using (−3)⁴ to find "total effect" of sequential temperature drops is mathematically nonsensical in context; the question is really just asking "what is (−3)⁴?" with a loosely attached narrative wrapper. The story does not justify why exponents are the right tool, and a student might reasonably expect the total temperature change to be negative (−12), not positive (81). The question is internally inconsistent between its scenario and its mathematical setup.

The hint ladder is appropriate for the exponent arithmetic and does not reveal the answer.

Difficulty: The item requires understanding that (−3)⁴ involves four negative factors, and tracking the sign through multiplication—a structural step beyond single-step arithmetic. This fits tier 5 (negative and power interaction). For grade 6–7, this is appropriately calibrated to exponent work.

**Audit verdict.** _(to fill in)_

### 10. `93c70aa6` — machine-REJECTED — algebra_1 / alg1_quadratics / d4

**Stem.** A rectangular table has a width of x cm and a length that is 7 cm more than its width. The area of the table is 30 square cm. What is the width of the table?

- **a)** 3 cm ← key
- **b)** -10 cm
- **c)** 5 cm
- **d)** 23 cm

**Equation.** `x**2 + 7*x - 30`  **Final answer.** 3 cm

1. Write an expression for the length in terms of the width x, then use the area formula for a rectangle.
2. The area is width times length, so x(x + 7) must equal 30. Expand and bring all terms to one side.
3. You will have a quadratic equation. Factor it or use another method to find the two solutions, then choose the one that makes sense for a width.

**Deterministic scorer.** answer key: derived answer disagrees
**Pipeline said.** symbolic answer x**2 + 7*x - 30 derived from the equation does not match declared correct option 'a' ('3 cm')

**Audit verdict.** _(to fill in)_

### 11. `ebb919aa` — machine-REJECTED — algebra_1 / alg1_quadratics / d4

**Stem.** A community garden is divided into two consecutive odd-numbered plots. The product of their plot numbers is 63. What is the smaller plot number?

- **a)** 21
- **b)** 7 ← key
- **c)** 9
- **d)** 5

**Equation.** `x**2 + 2*x - 63`  **Final answer.** 7

1. If the smaller plot number is x, write an expression for the next consecutive odd number.
2. The two plot numbers are x and x + 2, and their product equals 63.
3. Write the equation x(x + 2) = 63, expand it, and move all terms to one side to form a quadratic you can factor.

**Deterministic scorer.** answer key: derived answer disagrees
**Pipeline said.** symbolic answer x**2 + 2*x - 63 derived from the equation does not match declared correct option 'b' ('7')

**Audit verdict.** _(to fill in)_

### 12. `1bec466b` — machine-REJECTED — algebra_1 / alg1_quadratics / d5

**Stem.** A rectangular poster has a length that is 4 cm more than its width. The area of the poster is 96 square centimetres. What is the width of the poster?

- **a)** -12 cm
- **b)** 12 cm
- **c)** 8 cm ← key
- **d)** 10 cm

**Equation.** `x**2 + 4*x - 96`  **Final answer.** 8 cm

1. Let the width be x cm. What expression represents the length, and how do you write the area?
2. The area is x multiplied by (x + 4), and that product equals 96. Write that equation.
3. Expand to get x² + 4x = 96, then move 96 to the left to form x² + 4x - 96 = 0. Now factor or use the quadratic formula.

**Deterministic scorer.** answer key: derived answer disagrees
**Pipeline said.** symbolic answer x**2 + 4*x - 96 derived from the equation does not match declared correct option 'c' ('8 cm')

**Audit verdict.** _(to fill in)_

### 13. `66e03bd5` — machine-REJECTED — algebra_1 / alg1_quadratics / d5

**Stem.** A rectangular window has a width of x meters and a length 6 meters more than its width. The area of the window is 91 square meters. What is the width?

- **a)** -13 meters
- **b)** 85 meters
- **c)** 13 meters
- **d)** 7 meters ← key

**Equation.** `x**2 + 6*x - 91`  **Final answer.** 7 meters

1. Write an expression for the length in terms of the width x, then write the area formula for a rectangle.
2. The area is width times length, so x(x + 6) = 91. Expand the left side to get a quadratic equation.
3. Rearrange to standard form x² + 6x - 91 = 0, then factor or use the quadratic formula. Remember that only positive widths make sense.

**Deterministic scorer.** answer key: derived answer disagrees
**Pipeline said.** symbolic answer x**2 + 6*x - 91 derived from the equation does not match declared correct option 'd' ('7 meters')

**Audit verdict.** _(to fill in)_

### 14. `6f29199c` — machine-REJECTED — pre_algebra / prealg_exponents / d5

**Stem.** An economic model tracks debt adjustment where the debt multiplier is -3 for 6 consecutive quarters, then the result is adjusted by dividing by the same multiplier raised to the 4th power. What is the final debt adjustment factor?

- **a)** -9
- **b)** 9 ← key
- **c)** 3
- **d)** 729

**Equation.** `Eq(x, (-3)**6 / (-3)**4)`  **Final answer.** 9

1. Write the debt multiplier raised to the 6th power in the numerator and the same base raised to the 4th power in the denominator.
2. Use the quotient rule for exponents: when dividing powers with the same base, subtract the exponents.
3. Calculate (-3) raised to the power of 2 and remember that squaring a negative number gives a positive result.

**Deterministic scorer.** age-appropriate wording
**Pipeline said.** a sentence has 32 words, exceeding the 30-word readability ceiling: 'An economic model tracks debt adjustment where the debt mult'

**Audit verdict.** _(to fill in)_

### 15. `cda3a211` — machine-REJECTED — algebra_1 / alg1_quadratics / d5

**Stem.** A rectangular garden has a length that is 2 metres longer than its width. The area of the garden is 168 square metres. What is the width of the garden?

- **a)** 12 metres ← key
- **b)** -14 metres
- **c)** 14 metres
- **d)** 10 metres

**Equation.** `x**2 + 2*x - 168`  **Final answer.** 12 metres

1. Write an expression for the area using width x and length in terms of x.
2. The area is width times length: x times (x + 2) equals 168.
3. Expand to get a quadratic equation, move everything to one side, then factor or use the quadratic formula.

**Deterministic scorer.** answer key: derived answer disagrees, duplicate scenario (skeleton collision)
**Pipeline said.** symbolic answer x**2 + 2*x - 168 derived from the equation does not match declared correct option 'a' ('12 metres')

**Audit verdict.** _(to fill in)_

### 16. `0bc6b693` — machine-ACCEPTED — g2_subtraction / g2_sub_two_digit / d1

**Stem.** Liam has 50 stickers and uses 10 stickers to decorate his notebook. How many stickers does he have left?

- **a)** 10 stickers
- **b)** 60 stickers
- **c)** 40 stickers ← key
- **d)** 50 stickers

**Equation.** `Eq(x, 50 - 10)`  **Final answer.** 40 stickers

1. Think about what happens when Liam uses some of his stickers.
2. You need to subtract the number of stickers used from the number he started with.
3. Write 50 minus 10 and find the result.

**Deterministic scorer.** clean

**Audit verdict.** _(to fill in)_

### 17. `44477f9f` — machine-ACCEPTED — linear_equations / linear_two_step / d1

**Stem.** A streaming service charges a $7 setup fee and then $6 per month. Liam's total charge is $43. For how many months did he subscribe?

- **a)** 7 months
- **b)** 8 months
- **c)** 36 months
- **d)** 6 months ← key

**Equation.** `Eq(7 + 6*m, 43)`  **Final answer.** 6 months

1. Write an expression for Liam's total charge if he subscribed for m months.
2. His total is 7 + 6m dollars, and that equals 43.
3. Subtract the setup fee from both sides, then divide by the monthly rate.

**Deterministic scorer.** clean

**Audit verdict.** _(to fill in)_

### 18. `e37e2916` — machine-ACCEPTED — g1_addition / g1_add_within_10 / d1

**Stem.** Leo picks 4 apples from the first tree and 3 apples from the second tree. How many apples does Leo have?

- **a)** 8 apples
- **b)** 7 apples ← key
- **c)** 1 apple
- **d)** 6 apples

**Equation.** `Eq(x, 4 + 3)`  **Final answer.** 7 apples

1. Leo picks apples from two different trees. You need to find the total number of apples.
2. Write an addition to combine the apples from the first tree and the apples from the second tree.
3. Add 4 and 3 together to find how many apples Leo has in all.

**Deterministic scorer.** clean

**Audit verdict.** _(to fill in)_

### 19. `0e365340` — machine-ACCEPTED — linear_equations / linear_two_step / d2

**Stem.** A gym charges a $15 registration fee and $8 per fitness class. Jordan paid $63 in total. How many classes did Jordan take?

- **a)** 9 classes
- **b)** 8 classes
- **c)** 48 classes
- **d)** 6 classes ← key

**Equation.** `Eq(15 + 8*t, 63)`  **Final answer.** 6 classes

1. Write an expression for Jordan's total cost if t classes were taken.
2. The total cost is the registration fee plus the per-class fee times the number of classes: 15 + 8t, and that equals 63.
3. Subtract the registration fee from both sides, then divide by the per-class cost.

**Deterministic scorer.** clean

**Audit verdict.** _(to fill in)_

### 20. `3224d9fd` — machine-ACCEPTED — g1_addition / g1_add_within_10 / d2

**Stem.** Leo catches 1 butterfly in the morning and 7 butterflies in the afternoon. How many butterflies does he catch in total?

- **a)** 6 butterflies
- **b)** 7 butterflies
- **c)** 9 butterflies
- **d)** 8 butterflies ← key

**Equation.** `Eq(x, 1 + 7)`  **Final answer.** 8 butterflies

1. Think about how many butterflies Leo caught at each time of day.
2. You need to combine the morning butterflies and the afternoon butterflies.
3. Write an addition sentence with 1 butterfly and 7 butterflies.

**Deterministic scorer.** clean

**Audit verdict.** _(to fill in)_

### 21. `b33f982d` — machine-ACCEPTED — g1_addition / g1_add_within_10 / d2

**Stem.** Leo reads 3 books on Monday and 2 books on Tuesday. How many books does he read altogether?

- **a)** 6 books
- **b)** 4 books
- **c)** 1 book
- **d)** 5 books ← key

**Equation.** `Eq(x, 3 + 2)`  **Final answer.** 5 books

1. Think about how to combine the books from both days.
2. When you join two groups of items, you add the numbers.
3. Write the addition 3 + 2 and count on from 3.

**Deterministic scorer.** clean

**Audit verdict.** _(to fill in)_

### 22. `fe923051` — machine-ACCEPTED — linear_equations / linear_two_step / d2

**Stem.** A parking garage charges a $16 entry fee plus $7 for each hour parked. Maya's total charge is $51. How many hours did she park?

- **a)** 9 hours
- **b)** 35 hours
- **c)** 7 hours
- **d)** 5 hours ← key

**Equation.** `Eq(16 + 7*h, 51)`  **Final answer.** 5 hours

1. Write an expression for Maya's total charge if she parked for h hours.
2. Her total charge is 16 + 7h dollars, and that equals 51.
3. Subtract the entry fee from both sides, then divide by the hourly rate.

**Deterministic scorer.** clean

**Audit verdict.** _(to fill in)_

### 23. `0d6a32da` — machine-ACCEPTED — g3_word_problems / g3_wp_mixed / d3

**Stem.** A library orders 32 boxes of books. Each box contains 14 books. The library then lends 195 books to another library. How many books remain?

- **a)** 253 books ← key
- **b)** 448 books
- **c)** 643 books
- **d)** 241 books

**Equation.** `Eq(x, (32 * 14) - 195)`  **Final answer.** 253 books

1. How many books did the library receive in total from all the boxes?
2. Multiply the number of boxes by the books per box to find the starting total, then think about what happens when books are lent out.
3. Write an equation: the books remaining equal the total received minus the books lent.

**Deterministic scorer.** clean

**Audit verdict.** _(to fill in)_

### 24. `24aa1bbf` — machine-ACCEPTED — g4_multiplication_division / g4_div_by_one_digit / d3

**Stem.** A librarian arranges 2,763 books equally into 9 sections. How many books are in each section?

- **a)** 24867 books
- **b)** 307 books ← key
- **c)** 306 books
- **d)** 2754 books

**Equation.** `Eq(9 * x, 2763)`  **Final answer.** 307 books

1. If each of the 9 sections has the same number of books, what operation relates the total to the size of one section?
2. The total 2,763 is 9 times the number in one section.
3. Set up 9 times an unknown equal to 2,763, then divide both sides by 9.

**Deterministic scorer.** clean

**Audit verdict.** _(to fill in)_

### 25. `5961a716` — machine-ACCEPTED — pre_algebra / prealg_exponents / d3

**Stem.** An origami artist prepares paper for a class. She stacks 5^4 sheets into groups, with each group containing 5^2 sheets. How many groups does she create?

- **a)** 5 groups
- **b)** 25 groups ← key
- **c)** 2 groups
- **d)** 625 groups

**Equation.** `Eq(x, 5**4 / 5**2)`  **Final answer.** 25 groups

1. Calculate how many sheets she has in total by evaluating 5^4.
2. Each group holds 5^2 sheets, so divide the total sheets by the number per group.
3. Write the division 5^4 ÷ 5^2 and use the exponent rule for division with the same base.

**Deterministic scorer.** clean

**Audit verdict.** _(to fill in)_

### 26. `6471b751` — machine-ACCEPTED — g3_word_problems / g3_wp_mixed / d3

**Stem.** A school receives 36 boxes of pencils with 25 pencils in each box. The school then distributes 215 pencils to classrooms. How many pencils does the school have left?

- **a)** 470 pencils
- **b)** 1115 pencils
- **c)** 900 pencils
- **d)** 685 pencils ← key

**Equation.** `Eq(x, (36 * 25) - 215)`  **Final answer.** 685 pencils

1. First find the total number of pencils that arrived at the school.
2. Multiply the number of boxes by the pencils in each box, then subtract the pencils that were given out.
3. Write the calculation as 36 times 25, then take away 215.

**Deterministic scorer.** clean

**Audit verdict.** _(to fill in)_

### 27. `4b29e62b` — machine-ACCEPTED — trigonometry / trig_functions / d4

**Stem.** A robotic arm rotates through an angle of 4π/3 radians from its starting position. The horizontal displacement component of the arm's tip is given by the cosine of the rotation angle. What is cos(4π/3)?

- **a)** -√3/2
- **b)** -1/2 ← key
- **c)** √3/2
- **d)** 1/2

**Equation.** `Eq(x, cos(4*pi/3))`  **Final answer.** -1/2

1. Determine which quadrant contains the angle 4π/3 and recall the sign of cosine in that quadrant.
2. The angle 4π/3 is equivalent to 240°, which lies in the third quadrant where both sine and cosine are negative. Find the reference angle by subtracting π.
3. The reference angle is 4π/3 - π = π/3. Use cos(4π/3) = -cos(π/3) and recall the exact value of cos(π/3).

**Deterministic scorer.** clean

**Audit verdict.** _(to fill in)_

### 28. `814b05a0` — machine-ACCEPTED — pre_algebra / prealg_exponents / d4

**Stem.** A science experiment tracks a changing population of microbes in a controlled chamber. Each cycle the population multiplies by -2, representing alternating growth and decline. After 5 cycles, what is the population change value?

- **a)** -64 units
- **b)** 32 units
- **c)** -10 units
- **d)** -32 units ← key

**Equation.** `Eq(x, (-2)**5)`  **Final answer.** -32 units

1. When a number is raised to a power, you multiply that number by itself as many times as the exponent says.
2. Here you need (-2) × (-2) × (-2) × (-2) × (-2). Track the sign carefully after each multiplication.
3. Multiply pairs first: (-2) × (-2) = 4, then 4 × (-2) = -8, and continue. An odd number of negative factors gives a negative product.

**Deterministic scorer.** clean

**Audit verdict.** _(to fill in)_

### 29. `59a25b98` — machine-ACCEPTED — g3_word_problems / g3_wp_mixed / d5

**Stem.** A sports equipment store receives 50 boxes of tennis balls with 14 balls in each box. The store then sells 220 tennis balls to customers. How many tennis balls remain in the store?

- **a)** 480 tennis balls ← key
- **b)** 700 tennis balls
- **c)** 920 tennis balls
- **d)** 260 tennis balls

**Equation.** `Eq(x, (50 * 14) - 220)`  **Final answer.** 480 tennis balls

1. First find the total number of tennis balls the store received by multiplying the number of boxes by the balls in each box.
2. Now that you know how many tennis balls arrived, think about what happens when some are sold.
3. Write the total received minus the number sold to find how many remain.

**Deterministic scorer.** clean

**Audit verdict.** _(to fill in)_

### 30. `a2366bfc` — machine-ACCEPTED — g5_word_problems / g5_wp_ratios_mixed / d5

**Stem.** Two friends collect 45 stickers and decide to split them in the ratio 2:7. How many stickers does the friend with the larger share receive?

- **a)** 28 stickers
- **b)** 35 stickers ← key
- **c)** 315 stickers
- **d)** 7 stickers

**Equation.** `Eq(x, 45 * 7 / 9)`  **Final answer.** 35 stickers

1. Find the total number of parts in the ratio by adding 2 and 7 together.
2. The friend with the larger share gets 7 parts out of every 9 parts total.
3. Multiply 45 by 7, then divide by 9 to find how many stickers are in the 7-part share.

**Deterministic scorer.** clean

**Audit verdict.** _(to fill in)_
